# Integração de correções

1. Reproduza problemas de CMake, link, bundle ou ZIP com os frameworks sintéticos e adicione um teste ao probe quando a regressão puder ser representada localmente.
2. Revise a mudança no probe e rode os testes de host. Para mudanças de iPhoneOS, confirme o job macOS antes de gastar um run no build integrado privado.
3. Aplique manualmente no repositório privado o menor diff de infraestrutura equivalente. Registre lá a revisão pública de origem e preserve a licença e atribuição do trecho reutilizado.
4. Para uma correção descoberta no port privado, descreva a falha em termos genéricos, reproduza com um fixture novo e reimplemente na árvore pública. Use somente dados sintéticos no patch e nas evidências.

Antes de qualquer publicação futura, compare o diff e `git ls-files` com o inventário, confirme autor e conteúdo de cada commit a publicar e rode `python -B tools/check_public_tree.py`. O verificador usa uma lista de arquivos, examina o índice, a árvore relevante e os blobs do histórico alcançável e procura sinais de binários, material gerado, segredos e caminhos pessoais. A revisão humana cobre dados ou bibliotecas incorporados em arquivos de texto, metadados Git e linhas de log que escapem às heurísticas. Adicione cada dependência somente após conferir origem, revisão, licença e avisos de atribuição.

Mantenha os logs reais, credenciais, certificados, artefatos e dados do port em ambiente privado. Em issues públicas, use as saídas sintéticas ou um trecho revisado que contenha somente informações necessárias ao diagnóstico. Mantenha o histórico do probe independente, com patches de infraestrutura revisados individualmente.
