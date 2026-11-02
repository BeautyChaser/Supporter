"""Discovery invalidation must work before the machine's first TTL elapses.

All CLI calls are in-memory mocks. Time is controlled without sleeping or
launching the user's installed backends.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from supporter import backend_plugins
from supporter.backends import Backend,DEFAULT

ROOT=Path(__file__).resolve().parent.parent
BOOT_TIMES=(0,5,179)


class CacheBootClockTests(unittest.TestCase):
    @contextmanager
    def registry(self,now,*,error=False):
        with tempfile.TemporaryDirectory(prefix='cache-boot-clock-',dir=ROOT/'.runtime') as directory:
            root=Path(directory);executable=root/'fixture-agent.exe';executable.write_bytes(b'owned fixture, never executable')
            description={'schemaVersion':1,'id':'boot-clock-fixture','adapter':'generic',
                'detect':{'commands':[str(executable)],'versionArgs':['--version']},
                'models':{'values':['fixture-model']},'reasoning':{'*':['low']},'generate':{'args':[]}}
            (root/'fixture.json').write_text(json.dumps(description),encoding='utf-8')
            clock=SimpleNamespace(now=float(now));calls=[]
            def call(path,args,timeout=20):
                self.assertEqual(Path(path),executable);self.assertEqual(args,['--version'])
                calls.append((path,list(args)))
                if error:raise RuntimeError('fixture version unavailable')
                return 'fixture-agent 1.0.'+str(len(calls))
            ctx=SimpleNamespace(ROOT=root,Backend=Backend,DEFAULT=DEFAULT,call=Mock(side_effect=call))
            with patch.dict(os.environ,{'SUPPORTER_BACKEND_DIR':str(root)}),patch.object(backend_plugins,'_cache',{}),patch.object(backend_plugins.time,'monotonic',side_effect=lambda:clock.now):
                yield SimpleNamespace(clock=clock,ctx=ctx,calls=calls)

    def discover(self,fixture,*,presence=False):
        values=backend_plugins.discover(fixture.ctx,presence=presence)
        self.assertEqual(len(values),1);return values[0]

    def test_invalidate_survives_presence_and_reprobes_at_early_boot_times(self):
        for now in BOOT_TIMES:
            with self.subTest(monotonic=now),self.registry(now) as fixture:
                first=self.discover(fixture);self.assertEqual(first.status,'available')
                self.assertEqual(len(fixture.calls),1)
                backend_plugins.invalidate()
                for _ in range(3):
                    present=self.discover(fixture,presence=True)
                    self.assertEqual(present.version,first.version)
                    self.assertEqual(len(fixture.calls),1,'presence must not execute CLI probes')
                refreshed=self.discover(fixture)
                self.assertEqual(len(fixture.calls),2,'ordinary discovery must honor explicit invalidation at boot')
                self.assertNotEqual(refreshed.version,first.version)
                self.discover(fixture);self.assertEqual(len(fixture.calls),2,'the refreshed result should be cached again')

    def test_repeated_invalidate_is_idempotent_until_discovery_and_works_again_afterward(self):
        for now in BOOT_TIMES:
            with self.subTest(monotonic=now),self.registry(now) as fixture:
                self.discover(fixture)
                for _ in range(3):
                    backend_plugins.invalidate();self.discover(fixture,presence=True)
                self.assertEqual(len(fixture.calls),1)
                self.discover(fixture);self.assertEqual(len(fixture.calls),2)
                backend_plugins.invalidate();backend_plugins.invalidate()
                self.discover(fixture,presence=True);self.assertEqual(len(fixture.calls),2)
                self.discover(fixture);self.assertEqual(len(fixture.calls),3)

    def test_without_invalidate_normal_model_ttl_starts_at_actual_cache_time(self):
        for now in BOOT_TIMES:
            with self.subTest(monotonic=now),self.registry(now) as fixture:
                first=self.discover(fixture)
                fixture.clock.now=now+backend_plugins.MODEL_TTL-.001
                self.assertEqual(self.discover(fixture).version,first.version)
                self.assertEqual(len(fixture.calls),1,'young cache should be reused even near the TTL boundary')
                fixture.clock.now=now+backend_plugins.MODEL_TTL
                self.discover(fixture,presence=True);self.assertEqual(len(fixture.calls),1)
                refreshed=self.discover(fixture)
                self.assertEqual(len(fixture.calls),2,'cache must expire at its normal TTL boundary')
                self.assertNotEqual(refreshed.version,first.version)

    def test_unavailable_cache_honors_invalidation_and_its_shorter_ttl(self):
        for now in BOOT_TIMES:
            with self.subTest(monotonic=now),self.registry(now,error=True) as fixture:
                self.assertEqual(self.discover(fixture).status,'unavailable')
                backend_plugins.invalidate();self.discover(fixture,presence=True)
                self.assertEqual(len(fixture.calls),1)
                self.discover(fixture);self.assertEqual(len(fixture.calls),2)
                fixture.clock.now=now+29.999
                self.discover(fixture);self.assertEqual(len(fixture.calls),2)
                fixture.clock.now=now+30
                self.discover(fixture);self.assertEqual(len(fixture.calls),3)

    def test_invalidate_empty_cache_does_not_make_presence_launch_a_cli(self):
        for now in BOOT_TIMES:
            with self.subTest(monotonic=now),self.registry(now) as fixture:
                backend_plugins.invalidate();backend_plugins.invalidate()
                present=self.discover(fixture,presence=True)
                self.assertEqual(present.status,'checking');self.assertTrue(present.error)
                self.assertEqual(fixture.calls,[])
                self.assertEqual(self.discover(fixture).status,'available')
                self.assertEqual(len(fixture.calls),1)


if __name__=='__main__':unittest.main()
