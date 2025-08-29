---
title: "Static Web AppsにEntraマルチテナント認証を構成する"
emoji: "📚"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["azure", "static-web-apps", "entra-id"]
published: false
---

## はじめに
こんにちは、[be3](https://twitter.com/Blossomrail) です。

Azure Static Web Apps（以下、SWA）には、認証の機能があるのはご存知でしょうか？  
SWAは、Azure上でホストされる静的なWebアプリケーションを簡単にデプロイできるサービスですが、認証機能を使用することで、認証されたユーザーだけがアプリケーションを利用できるようにしてセキュリティを高めることができます。

そんなSWAの認証機能ですが、Entra IDを使用したマルチテナント認証を構成することができます。
エンタープライズのアプリケーションを、自社Entraテナントのユーザーだけでなくビジネス的な繋がりのある外部テナントのユーザー（グループ会社やビジネスパートナーなど）も利用できるようにしたいシナリオは少なくないのではないでしょうか。
さらに、特定のテナントやユーザー、グループに限定して、アプリケーションを利用できるようにしたいケースもあると思います。
:::message
後述しますが、単にEntra IDのマルチテナントアプリを登録するだけでは、全てのEntraテナントのユーザーが利用できるようになってしまいます。 
:::

そこで本記事では、以下の図のようなシナリオを想定して、SWAにおけるEntraマルチテナント認証の構成とアクセス制御の方法を紹介します。
<!-- TODO: 図の挿入 -->

また、今回のシナリオを検証したコードは以下のリポジトリで公開しています。
https://github.com/your-repo
Entra IDの設定に関しては対象外ですが、SWAの構成ファイルや環境変数の設定、バックエンドのテナント制限バリデーションの実装などが含まれていますので、興味のある方はぜひご覧ください。
そして、不備や改善点があれば、ぜひIssueやPRをお待ちしています。

## SWAの認証機能について
手順の解説に入る前に、SWAの認証機能について簡単に整理しておきます。
SWAには、Entra IDを使用した認証機能が2種類あります。

1. マネージド認証（既定値）
2. カスタム認証

### マネージド認証
[マネージド認証](https://learn.microsoft.com/ja-jp/azure/static-web-apps/authentication-authorization)は、認証プロバイダーにEntra IDまたはGitHubを使用して、ユーザーの認証を行う機能です。
:::message
マネージド認証は、SWAのFreeプランから利用可能です。
:::
ユーザーは、サービスによって予め定義されたサインインとサインアウトのパス（Entra IDの場合は、`/.auth/login/aad`と`/.auth/logout`）を、構成ファイル `staticwebapp.config.json` に記述するか、またはUI上にリンクを追加することで、フロントエンドに簡単に認証を設けることができます。  
例えば、以下の記述では、認証されたユーザーだけがアプリケーションにアクセスできるようにし、認証されていないユーザーは、`/.auth/login/aad` にリダイレクトされるように設定しています。
```json:staticwebapp.config.json
{
  "navigationFallback": {
    "rewrite": "/index.html"
  },
  "routes": [
    {
      "route": "/*",
      "allowedRoles": [ "authenticated" ]
    }
  ],
  "responseOverrides": {
    "401": {
      "statusCode": 302,
      "redirect": "/.auth/login/aad"
    }
  }
}
```
構成ファイル `staticwebapp.config.json` の各種プロパティについては、[こちら](https://learn.microsoft.com/ja-jp/azure/static-web-apps/configuration)を参照してください。
マネージド認証を設定する詳細な手順は、[こちら](https://learn.microsoft.com/ja-jp/azure/static-web-apps/add-authentication)を参照してください。

このように、マネージド認証を使用する場合、ユーザーはEntra IDのアプリケーション登録をする必要がない点がポイントです。
実際には、サービス側でマルチテナントアプリケーションを登録して、ユーザーはそのアプリケーションにサインインする形になります。<!-- TODO: 要検証 -->
詳しくは、以下のブログが参考になります。
https://ayuina.github.io/ainaba-csa-blog/auth-static-webapp/#:~:text=%E6%97%A2%E5%AE%9A%E3%81%A7%E6%9C%89%E5%8A%B9%E3%81%AB%E3%81%AA%E3%81%A3%E3%81%A6%E3%81%84%E3%82%8B%E8%AA%8D%E8%A8%BC%EF%BC%88Managed%20Authentication%EF%BC%89%E3%81%AF%E3%80%81Azure%20Static%20Web%20Apps%20(Application%20ID%20%3D%3D%20d414ee2d%2D73e5%2D4e5b%2Dbb16%2D03ef55fea597)%20%E3%81%A8%E3%81%84%E3%81%86%E3%83%9E%E3%83%AB%E3%83%81%E3%83%86%E3%83%8A%E3%83%B3%E3%83%88%E3%82%A2%E3%83%97%E3%83%AA%E3%82%B1%E3%83%BC%E3%82%B7%E3%83%A7%E3%83%B3%E3%81%AB%E5%AF%BE%E3%81%97%E3%81%A6%E8%AA%8D%E8%A8%BC%E3%82%92%E8%A1%8C%E3%81%86%E4%BB%95%E6%8E%9B%E3%81%91%E3%81%AB%E3%81%AA%E3%81%A3%E3%81%A6%E3%81%84%E3%81%BE%E3%81%99%E3%80%82%20%E3%81%93%E3%81%AE%E3%81%9F%E3%82%81%E3%83%A6%E3%83%BC%E3%82%B6%E3%83%BC%E3%81%8C%E6%89%80%E5%B1%9E%E3%81%99%E3%82%8B%E4%BB%BB%E6%84%8F%E3%81%AE%E3%83%86%E3%83%8A%E3%83%B3%E3%83%88%E3%81%AB%E5%AF%BE%E3%81%97%E3%81%A6%E8%AA%8D%E8%A8%BC%E3%82%92%E5%A7%94%E8%A8%97%E3%81%99%E3%82%8B%E3%81%93%E3%81%A8%E3%81%8C%E5%87%BA%E6%9D%A5%E3%82%8B%E3%82%88%E3%81%86%E3%81%AB%E3%81%AA%E3%81%A3%E3%81%A6%E3%81%84%E3%82%8B%E3%82%8F%E3%81%91%E3%81%A7%E3%81%99%E3%80%82

### カスタム認証
一方、[カスタム認証](https://learn.microsoft.com/ja-jp/azure/static-web-apps/authentication-custom?tabs=aad%2Cinvitations)は、Entra IDはもちろんのこと、AppleやGoogle、その他OpenID Connect（OIDC）に準拠した認証プロバイダーを使用して、ユーザーの認証を行う機能です。
:::message
カスタム認証を使用するためには、SWAのStandardプランが必要になります。
:::

カスタム認証の場合も、マネージド認証と同様にルートを設定しますが、認証プロバイダーの設定を構成ファイル `staticwebapp.config.json` に別途記述する必要があります。
そのため、構成ファイルを記述する前に、認証プロバイダー側でアプリケーションの登録を行い、クライアントIDやクライアントシークレットを取得しておく必要があります。
例えば、Entra IDを認証プロバイダーに使用する場合は、構成ファイル `staticwebapp.config.json` の `auth` セクションに以下の記述を追加します。
```json:staticwebapp.config.json
{
  "auth": {
    "identityProviders": {
      "azureActiveDirectory": {
        "registration": {
          "openIdIssuer": "https://login.microsoftonline.com/<TENANT_ID>/v2.0",
          "clientIdSettingName": "AZURE_CLIENT_ID",
          "clientSecretSettingName": "AZURE_CLIENT_SECRET_APP_SETTING_NAME"
        }
      }
    }
  }
}
```
`<TENANT_ID>` の箇所には、Entra IDのテナントIDまたは `common` を指定できます。
ここでテナントIDを指定した場合は、シングルテナント認証となり、指定したテナントのユーザーだけがアプリケーションにアクセスできるようになります。
`AZURE_CLIENT_ID` と `AZURE_CLIENT_SECRET_APP_SETTING_NAME` の箇所は編集する必要はないですが、SWAに以下の名前の環境変数を設定しておく必要があります。
環境変数の名前を `staticwebapp.config.json` に記述したものと一致させておく必要があるので注意してください。
- `AZURE_CLIENT_ID` : Entra IDのアプリケーション登録の際に取得したクライアントID
- `AZURE_CLIENT_SECRET_APP_SETTING_NAME` : Entra IDのアプリケーション登録の際に取得したクライアントシークレット


### Entra IDを認証プロバイダーに使用する場合のマネージド認証とカスタム認証の違い
Entra IDを認証プロバイダーに使用する場合のマネージド認証とカスタム認証の重要な相違点は、アプリケーション登録をする必要があるかどうかです。
アプリケーション登録を自前で行う必要があるカスタム認証の場合、Entra IDでエンタープライズアプリケーション（サービスプリンシパル）として管理できるようになるため、ユーザーやグループをアプリケーションに割り当てたり、条件付きアクセスポリシーを適用したりといったEntra IDの機能を利用できる点がメリットです。

ここから本題に入っていきますが、今回紹介するSWAのEntraマルチテナント認証は、後者のカスタム認証を使用した方法になります。

## カスタム認証を使用したマルチテナント認証の構成
### Entraマルチテナントアプリの登録
まず、Entra IDのポータルにアクセスして、マルチテナントアプリケーションを登録します。
ここで、クライアントIDとクライアントシークレットを取得しておきます。

### 構成ファイル `staticwebapp.config.json`の編集
次に、SWAの構成ファイル `staticwebapp.config.json` を編集します。
以下のように、`auth` セクションを追加します。
```json:staticwebapp.config.json
{
  "auth": {
    "identityProviders": {
      "azureActiveDirectory": {
        "registration": {
          "openIdIssuer": "https://login.microsoftonline.com/common/v2.0",
          "clientIdSettingName": "AZURE_CLIENT_ID",
          "clientSecretSettingName": "AZURE_CLIENT_SECRET_APP_SETTING_NAME"
        }
      }
    }
  }
}
```
ここで重要なのは、`openIdIssuer` の値でテナントIDではなく `common` を指定している点です。
これで、SWAのアプリケーションにサインインしたユーザーは、Entra IDのマルチテナントアプリケーションにサインインすることになります。

### SWAの環境変数の設定
次に、SWAの環境変数を設定します。
AzureポータルのSWAのリソースにアクセスして、左側のメニューから「構成」を選択します。

```json
{
  "AZURE_CLIENT_ID": "<CLIENT_ID>",
  "AZURE_CLIENT_SECRET_APP_SETTING_NAME": "<CLIENT_SECRET>"
}
```
`<CLIENT_ID>` と `<CLIENT_SECRET>` の箇所には、Entra IDのアプリケーション登録の際に取得したクライアントIDとクライアントシークレットをそれぞれ設定します。

### 動作確認
テナントの異なるユーザーでそれぞれサインインして、アプリケーションにアクセスできることを確認します。

まずは、テナントAのユーザーでサインインして、アプリケーションにアクセスできることを確認します。
次に、テナントBのユーザーでサインインして、アプリケーションにアクセスできることを確認します。
最後に、テナントCのユーザーでサインインして、アプリケーションにアクセスできないことを確認します。

このように、マルチテナントアプリケーションを登録することで、複数のテナントのユーザーがアプリケーションにアクセスできるようになりますが、全てのテナントのユーザーがアクセスできるようになってしまいます。
以降では、特定のテナントやユーザー、グループに限定して、アプリケーションを利用できるようにする方法を紹介します。

## 特定のテナントにアクセスを制限する
まずは、特定のテナントにアクセスを制限する方法を紹介します。
### ユーザーの認証情報を取得する

### 認証結果をバリデーションするミドルウェアを実装する


### 動作確認


## 特定のユーザー、グループにアクセスを制限する
次に、特定のユーザー、グループにアクセスを制限する方法を紹介します。

### マルチテナントアプリケーションの同意後のサービスプリンシパルの複製
マルチテナントアプリケーションを登録した後、Entra IDのポータルにアクセスして、左側のメニューから「エンタープライズアプリケーション」を選択します。
ここで、マルチテナントアプリケーションのサービスプリンシパルが複製されていることを確認します。
このサービスプリンシパルは、Entra IDのポータルからは確認できませんが、Azure CLIやPowerShellを使用して確認することができます。

### サービスプリンシパルにユーザー、グループを割り当てる
Entra IDのポータルにアクセスして、左側のメニューから「エンタープライズアプリケーション」を選択します。
ここで、マルチテナントアプリケーションのサービスプリンシパルを選択して、「ユーザーとグループ」を選択します。
ここで、ユーザーやグループを割り当てることができます。

### 動作確認
テナントの異なるユーザーでそれぞれサインインして、アプリケーションにアクセスできることを確認します。

## おわりに
SWAにEntraマルチテナント認証を構成する方法とアクセス制御の方法について紹介しました。
今回は、SWA x マルチテナントアプリという組み合わせでしたが、App ServiceやAzure Functionsなど、他のAzureサービスでも同様の構成が可能です。

余談ですが、App Serviceのドキュメントでは[マルチテナントのアプリ登録が明記](https://learn.microsoft.com/ja-jp/azure/app-service/configure-authentication-provider-aad?tabs=workforce-configuration#express)されていますが、SWAのドキュメントには記載がなかったり、このシナリオを紹介した個人ブログがなかったりと情報が少ないと思い、今回こちらの方法を紹介することにしました。

## 参考文献

