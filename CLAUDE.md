# このリポジトリ固有の Claude Code 規約

> **原則:** チーム共通の規約・コーディングスタイル・運用方針は `~/.claude/CLAUDE.md`(Starter Kit 管理)に書く。
> このファイルには **このリポジトリでしか通用しない情報** のみを書く。
> 迷ったら「他のリポでも同じか?」で判断 → 同じなら Starter Kit、違うならここ。

## 扱うデータ

<!-- TEMPLATE:data -->
- 例: 顧客マスタ(機密 / 社内限定)
- 例: Slack 投稿ログ(社外秘)
<!-- /TEMPLATE:data -->

## 連携する外部システム / API

<!-- TEMPLATE:external -->
- 例: GitHub API(リポ管理)
- 例: Slack Web API(通知)
- 例: Google Sheets API(集計結果出力)
<!-- /TEMPLATE:external -->

## 特殊な依存・制約

<!-- TEMPLATE:constraints -->
- 例: レガシー Oracle DB に ODBC 経由でアクセス
- 例: 社内 SSO(SAML)を経由しないと API が呼べない
<!-- /TEMPLATE:constraints -->

## デプロイ手順

<!-- TEMPLATE:deploy -->
- 例: 社内 Jenkins から `deploy.sh` を kick
- 例: 手動で社内サーバーに rsync
<!-- /TEMPLATE:deploy -->

## オーナー連絡先

<!-- TEMPLATE:contacts -->
- Primary: name <email>
- Slack: #channel
- On-call: PagerDuty schedule URL
<!-- /TEMPLATE:contacts -->

## このリポでだけ守るべき注意点

<!-- TEMPLATE:gotchas -->
- 例: テスト実行前に必ず社内 VPN 接続
- 例: `prod_*` テーブルへの書き込みは絶対禁止
<!-- /TEMPLATE:gotchas -->

---
