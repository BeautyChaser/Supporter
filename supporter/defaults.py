def default_model(backend):
    if backend.name=='codex':
        visible=backend.models
        for model in ('gpt-6-luna','gpt-5.6-luna'):
            if model in visible:return model
        return next((m for m in visible if 'luna' in m.lower()),visible[0])
    return backend.models[0]

def default_reasoning(backend,model):
    return 'low' if backend.name=='codex' and 'luna' in model.lower() and 'low' in backend.reasoning.get(model,[]) else 'default'
