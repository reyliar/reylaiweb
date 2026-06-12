# ReylAI Email Setup

Bu Worker artık Cloudflare Email Sending yerine Resend kullanır.

## Servis

Secilen servis: Resend Free

- Ucretsiz plan: 3.000 e-posta/ay, 100 e-posta/gun, 1 domain
- Gönderim: `no-reply@reyliar.xyz`
- Gelen posta:
  - `contact@reyliar.xyz` -> `mynamesreyli@gmail.com`
  - `reyli@reyliar.xyz` -> `mynamesreyli@gmail.com`
  - `alkim@reyliar.xyz` -> `alkimgencali99@gmail.com`
- Inbound webhook: `https://ai.reyliar.xyz/api/email/resend/inbound`
- Resend Receiving MX: `reyliar.xyz MX 10 inbound-smtp.us-east-1.amazonaws.com`
- Mail paneli: `https://mail.reyliar.xyz/`

## Resend paneli

1. Resend hesabinda `reyliar.xyz` domainini ekle.
2. Resend'in verdigi SPF/DKIM ve gerekiyorsa DMARC kayitlarini DNS'e ekle.
3. Receiving/Inbound özelliğini aç ve Resend'in verdiği MX kaydını DNS'e ekle.
4. Webhook oluştur:
   - URL: `https://ai.reyliar.xyz/api/email/resend/inbound`
   - Event: `email.received`
5. API key ve webhook signing secret degerlerini Worker secret olarak ekle:

```powershell
npx wrangler secret put RESEND_API_KEY
npx wrangler secret put RESEND_WEBHOOK_SECRET
```

## Worker env

`wrangler.jsonc` icinde:

- `RESEND_API_URL=https://api.resend.com`
- `CONTACT_FORWARD_TO=mynamesreyli@gmail.com`

`CONTACT_FORWARD_TO`, `contact@reyliar.xyz` adresine gelen postaların iletileceği adrestir.
`reyli@reyliar.xyz` ve `alkim@reyliar.xyz` Worker içindeki alias tablosuyla yönlendirilir.

## Mail paneli

`mail.reyliar.xyz` Worker Custom Domain olarak `reylai-api` Worker'ına bağlıdır. Cloudflare bu custom domain için DNS ve sertifika kaydını otomatik oluşturur.

Panel:

- `contact@reyliar.xyz` gelen kutusunu D1 `mail_messages` tablosundan okur.
- `contact@reyliar.xyz` adıyla Resend üzerinden cevap gönderir.
- Cevap e-postalarında ReylAI Contact HTML UI kullanılır.
- Session bilgilerini D1 `mail_sessions` tablosunda saklar.

Gerekli Worker ayarlari:

- `MAIL_PANEL_USER=reyliar`
- `MAIL_PANEL_PASSWORD` secret olarak tanimli olmalidir.

```powershell
npx wrangler secret put MAIL_PANEL_PASSWORD
```
