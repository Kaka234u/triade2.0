# FK Káka para Android

Aplicativo WebView para Android 7.0 ou superior. Abre exclusivamente a área FK do site hospedado no Render. Requer internet e o servidor disponível; não empacota o backend Flask nem o banco de dados.

## Baixar e instalar

No GitHub, abra Actions → APK FK Kaka → execução concluída → Artifacts → FK-Kaka-Android. Extraia o ZIP e transfira FK-Kaka-Android.apk para o celular. Abra o APK e permita a instalação por esse aplicativo quando o Android solicitar. Não precisa publicar em loja nem usar AWS.

O APK gerado é uma versão de demonstração assinada com chave de debug, para apresentação escolar. Uma nova execução pode usar outra chave: nesse caso, desinstale a versão anterior antes de instalar (a sessão local será apagada). Para distribuição definitiva, use uma chave de lançamento privada e estável; não a envie ao repositório.

## Recursos

- Ícone FK, sessão persistente, voltar pelo histórico e ajuste às barras e teclado do Android.
- Tela de falha com opção de tentar novamente; indisponibilidade do Render também pode causar essa tela.
- WhatsApp, telefone e links externos abrem em seus respectivos aplicativos.
- Seleção de arquivos pelo seletor do Android, sem permissão ampla de armazenamento.
- HTTPS obrigatório para o site, sem ignorar certificados inválidos ou adicionar ponte JavaScript nativa.

Downloads são abertos no navegador externo; arquivos privados podem exigir novo login nele. Notificações do site funcionam dentro do app aberto, sem push nativo em segundo plano. Este projeto não gera um aplicativo iOS.

## Desenvolvimento

Abra a pasta android no Android Studio, com JDK 17, Android SDK 35 e Gradle 8.11.1. O workflow instala as ferramentas e gera o APK automaticamente. Também é possível executar `gradle assembleDebug lintDebug` nesta pasta com Gradle instalado. Não há Gradle Wrapper incluído.

Antes da apresentação, teste no aparelho: abrir, entrar e sair da conta, voltar, girar a tela, enviar uma imagem, abrir WhatsApp, desligar a internet e reconectar. Use o modo de testes administrativo do site para não criar cobranças reais. O APK sempre carrega a versão atualmente publicada do site.
