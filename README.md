# iPhoneOS Infrastructure Probe

Aplicativo sintético para testar a infraestrutura de um port iOS. O app abre uma tela UIKit, chama uma função em dois frameworks encadeados e submete um command buffer Metal. Os fixtures usam conteúdo gerado pelos próprios testes.

## Windows

Use Git, CMake 3.25 ou superior, Ninja e Python 3.10 ou superior.

```powershell
python -B tools/check_public_tree.py
cmake -S . -B build/host -G Ninja
cmake --build build/host
ctest --test-dir build/host --output-on-failure
```

O build de host configura e executa testes Python com ZIPs e saídas Mach-O sintéticas. O código UIKit e os frameworks iOS exigem Xcode e o SDK iPhoneOS.

## macOS

Com Xcode, CMake, Ninja e Python instalados, execute em uma árvore de build limpa:

```sh
bash tools/build_iphoneos.sh
```

O script gera `PhoneOSProbe.app` para iPhoneOS ARM64 com mínimo iOS 16.3, inspeciona os três Mach-O e gera um IPA sem assinatura com dois relatórios em `out/iphoneos/`. Uma inspeção aprovada comprova o link e o empacotamento. Para executar a tela e o teste Metal, assine e provisione o app em ambiente controlado e use um iPhone.

## CI

O workflow manual executa primeiro a auditoria da árvore, a configuração CMake/Ninja e os fixtures em Windows. Depois executa a compilação iPhoneOS e a inspeção no macOS. Os relatórios aparecem no log da execução e os binários ficam no workspace temporário do runner. [Workflow](.github/workflows/iphoneos-probe.yml)

O [inventário e as licenças](docs/PROVENANCE.md) detalham a origem dos arquivos. O [processo de integração](docs/INTEGRATION.md) descreve como transferir correções com diffs pequenos.
