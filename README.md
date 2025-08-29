# Zenn CLI

* [📘 How to use](https://zenn.dev/zenn/articles/zenn-cli-guide)


```sh
# Preview
npx zenn preview
```

## scripts

このリポジトリに便利なスクリプトを追加しています。

- `scripts/add_spaces_around_english.py`
	- 概要: Markdown ファイル内の日本語と英単語（ASCII 文字列）の間に半角スペースを自動挿入します。コードブロック、インラインコード、リンク、画像、autolink は保護されます。
	- 使い方（デフォルトファイル `articles/aca-otel-tracing.md` に対して実行）:

```bash
python3 scripts/add_spaces_around_english.py
```

	- 任意のファイルに対して実行する例:

```bash
python3 scripts/add_spaces_around_english.py path/to/your.md
```

	- 実行すると対象ファイルと同じディレクトリにバックアップ（`.md.bak`）が作成されます。
