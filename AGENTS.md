# Versionamento do SME

- Não crie commit nem envie alterações ao Git sem pedido explícito do usuário.
- Cada novo commit deve ter uma versão exclusiva em `frontend/package.json`. Considere também os commits anteriores à adoção do versionamento: conte os commits existentes com `git rev-list --count HEAD` e prepare para o próximo commit `0.1.(contagem + 1)`. Com 15 commits existentes, a árvore local recebe `0.1.16` para o próximo commit; depois dele, o commit seguinte recebe `0.1.17`. Se a versão calculada já estiver preparada e ainda não tiver sido comitada, não incremente novamente. Inclua a mudança da versão no próprio commit.
- Enviar commits já existentes ao remoto não cria uma nova versão. Não reescreva os commits antigos para atribuir versões retroativamente.
- A versão exibida no menu de perfil deve continuar vindo de `frontend/package.json` no build. Valide o build do frontend antes de criar um commit versionado.
