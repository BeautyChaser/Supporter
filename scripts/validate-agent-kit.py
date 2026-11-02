"""Validate project skills, custom agents and local references."""
from pathlib import Path
import re
import tomllib
ROOT=Path(__file__).resolve().parent.parent
def validate():
    assert (ROOT/'AGENTS.md').is_file(),'Missing AGENTS.md'
    assert not (ROOT/'.agent').exists(),'Use .agents, not .agent'
    skills=list((ROOT/'.agents/skills').glob('*/SKILL.md'))
    for file in skills:
        value=file.read_text(encoding='utf-8');front=re.match(r'\A---\n(.*?)\n---\n',value,re.S)
        assert front,f'Missing skill frontmatter: {file.parent.name}'
        fields=dict(re.findall(r'^(name|description):\s*(.+)$',front[1],re.M))
        assert fields.get('name')==file.parent.name and fields.get('description'),'Invalid skill identity'
        assert len(fields['name'])<64 and re.fullmatch(r'[a-z0-9-]+',fields['name']),'Invalid skill name'
        for target in re.findall(r'\]\(([^)]+)\)',value):
            if '://' not in target:assert (file.parent/target).resolve().is_file(),f'Broken reference: {file.parent.name}'
    agents=list((ROOT/'.codex/agents').glob('*.toml'))
    for file in agents:
        data=tomllib.loads(file.read_text(encoding='utf-8'))
        assert all(isinstance(data.get(k),str) and data[k] for k in ('name','description','developer_instructions')),'Invalid agent definition'
    assert len(skills)==3 and len(agents)==3,'Incomplete agent kit'
    print('Agent kit valid: 3 skills, 3 custom agents and AGENTS.md.')
if __name__=='__main__':validate()
