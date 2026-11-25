# Procedência e licenças

## Referência Android

O repositório Android organiza o app em `android/` e `app/`, configuração em `config/`, SDK em `sdk/`, ferramentas em `tools/` e dependências em `thirdparty/`. Seu README descreve extração a partir dos discos do usuário, build da ferramenta de codegen no host, geração local e configuração, compilação, staging e montagem do APK. Usa LLVM, CMake, Ninja, JDK 17, SDK Android e NDK r28. O README fixa o ReXGlue v0.10.0, enquanto os avisos mencionam v0.10.1. Essa diferença exigiria conferir a revisão exata para reaproveitar o build. [README do Android](https://github.com/Lazaer-YZY/ds2-sotfs-recomp#building-from-source) · [Avisos de terceiros](https://github.com/Lazaer-YZY/ds2-sotfs-recomp/blob/main/THIRD_PARTY_NOTICES.md)

A política declarada exclui dados originais, chaves e código gerado do Git. O ignore cobre também logs, saídas de build e bibliotecas nativas do app. O SDK tem dependências obtidas separadamente e o AdrenoTools é um submódulo. O projeto declara GPL-3.0 e atribui os componentes derivados de DS2_switch, ReXGlue/Xenia, Lost Odyssey Recomp, AdrenoTools e Turnip. Os avisos distinguem as licenças de bibliotecas como SDL3 e FFmpeg e mencionam Turnip incluído no APK. A licença raiz e a existência de um APK público são insuficientes para autorizar redistribuição de conteúdo derivado do jogo. [Licença](https://github.com/Lazaer-YZY/ds2-sotfs-recomp/blob/main/LICENSE) · [Ignore](https://github.com/Lazaer-YZY/ds2-sotfs-recomp/blob/main/.gitignore) · [Submódulo](https://github.com/Lazaer-YZY/ds2-sotfs-recomp/blob/main/.gitmodules) · [Avisos de terceiros](https://github.com/Lazaer-YZY/ds2-sotfs-recomp/blob/main/THIRD_PARTY_NOTICES.md)

## Inventário desta árvore

| Arquivos | Origem e licença |
| --- | --- |
| `src/{main.m,ProbeBase.c,ProbePlugin.c}` | Aplicativo de teste e dois frameworks originais, MIT |
| `CMakeLists.txt`, `ios/Info.plist.in` | Configuração original, MIT |
| `tools/{build_iphoneos.sh,check_public_tree.py,inspect_ipa.py,inspect_macho.py}` | Ferramentas originais, MIT |
| `tests/test_infrastructure.py` | Fixtures originais, MIT |
| `.github/workflows/iphoneos-probe.yml`, `.gitignore` | Configuração original, MIT |
| `README.md`, `docs/{PROVENANCE.md,INTEGRATION.md}`, `LICENSE` | Documentação original e texto da licença MIT |

O workflow usa [actions/checkout](https://github.com/actions/checkout/blob/v4/LICENSE), MIT, GitHub, Inc. e contribuidores. CMake, Ninja, Python, Git e Xcode são ferramentas externas. Foundation, UIKit e Metal vêm do SDK do sistema e são vinculados pelo app. O inventário contém apenas os arquivos listados e nenhum binário dessas ferramentas ou frameworks de sistema.

## Exclusões

Ficam fora da árvore o jogo, assets, executáveis, dumps, DLC, código recompilado ou gerado, SDK e overlays do port, bibliotecas de terceiros sem revisão por arquivo, arquivos de configuração privados, certificados, credenciais, artefatos, capturas e logs. O projeto Android foi usado como referência documental. Seu código, assets, bibliotecas e histórico ficaram fora do inventário.

Vulkan e MoltenVK aguardam a escolha de revisões exatas, a revisão da cadeia transitiva de build e dos avisos aplicáveis, e uma verificação iPhoneOS separada. A referência atual do MoltenVK usa Apache-2.0. Vulkan-Headers identifica MIT e Apache-2.0 por arquivo. Nenhum desses componentes é necessário para o teste Metal do probe. [MoltenVK](https://github.com/KhronosGroup/MoltenVK/blob/main/LICENSE) · [Vulkan-Headers](https://github.com/KhronosGroup/Vulkan-Headers/blob/main/LICENSE.md)
