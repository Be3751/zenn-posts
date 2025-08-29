---
title: "Azure Container Apps で稼働するアプリケーションへ OpenTelemetry を導入して分散トレーシングを実現する"
emoji: "🔭"
type: "tech" # tech: 技術記事 / idea: アイデア
topics: ["azure", "container", "tracing", "opentelemetry"]
published: false
---

![alt text](/images/aca_otel_tracing_demo.png)

# はじめに
こんにちは、 [be3](https://twitter.com/Blossomrail) です！

突然ですが、分散トレーシングをご存知でしょうか？
アプリケーションを運用する中で、障害の発生箇所やパフォーマンス上のボトルネックを特定することは重要ですよね。特にマイクロサービスアーキテクチャを採用したアプリケーションでは、複数のサービスが連携して動作するため、サービス間の通信経路が複雑化する場合があります。また、プロセス間通信や外部サービスとの連携においても同様です。そうした場合、単一のサービスのログやメトリクスだけでは、問題の特定が難しくなることがあります。

これを解決するためのアプローチとして、分散トレーシングがあります。
分散トレーシングは、分散システムにおけるサービス間のリクエストの流れやレイテンシを追跡、可視化し、パフォーマンスのボトルネックやエラーの原因を特定する手法です。

本記事では、分散トレーシングや OpenTelemetry の基礎知識について触れつつ、 Azure Container Apps （以下、 ACA ） 上で動作するアプリケーションに [OpenTelemetry](https://opentelemetry.io/ja/docs/what-is-opentelemetry/) を導入し、 Application Insights や Azure Monitor などと連携して分散トレーシングを実現する方法を紹介します。

# OpenTelemetry とは
## OpenTelemetry の概要
[OpenTelemetry](https://opentelemetry.io/ja/docs/what-is-opentelemetry/) は、 Observability のための [CNCF (Cloud Native Computing Foundation) プロジェクト](https://www.cncf.io/projects/opentelemetry/) であり、ログ、メトリクス、トレースといったテレメトリーデータの収集と送信を統一的に行うためのライブラリとエージェントを提供します。（本記事では、分散トレーシングという表記は手法を指し、トレースという表記は分散トレーシングの結果として得られるテレメトリーデータを指し、区別して使い分けます。）

OpenTelemetry のライブラリやエージェントをアプリケーションに組み込むことで、アプリケーションのパフォーマンスや動作状況に関するテレメトリーデータを収集することができます。

:::message
ここで重要な点としては、 OpenTelemetry はテレメトリーデータの収集と送信を責務とする設計思想を持っており、可視化や保存、分析は責務の対象外となっていることです。[^1]
そのため、 OpenTelemetry を使用して収集したテレメトリーデータは、他のツール（ Azure では、 Application Insights や Azure Monitor ）と連携して可視化や分析を行うこととなります。
:::

## OpenTelemetry の技術的な優位性

OpenTelemetry は、分散トレーシングや可観測性の分野で以下のような技術的な優位性を持っています。

**1. ベンダーニュートラルな設計**

OpenTelemetryは特定の監視・APMベンダーに依存せず、標準化されたインターフェースとエクスポーター設計により、Datadog、New Relic、Azure Monitor、Jaegerなど様々なバックエンドと簡単に連携できます。これにより、ベンダーロックインを回避し、柔軟な運用が可能です。

**2. トレース／メトリクス／ログの統合仕様**

OTelはトレース・メトリクス・ログの3種類のテレメトリーデータを1つの仕様とSDKで扱えるため、従来のように複数のツールを組み合わせる必要がなく、一貫した方法でデータ収集・処理ができます。

**3. 多言語対応と豊富な自動計装**

主要な言語（Python, Java, Go, .NET, Node.js など）に対応し、requestsやFlaskなどのライブラリに対する自動計装も提供されています。これにより、既存アプリへの導入が容易で、最小限のコード変更で可観測性を追加できます。

**4. コンテキスト伝播の標準化（W3C Trace Context）**

OpenTelemetryはW3C Trace Contextというグローバル標準に基づくコンテキスト伝播仕様を採用しており、サービス間で一貫したトレースの引き継ぎが可能です。これにより、複雑なマイクロサービスアーキテクチャでもエンドツーエンドの可観測性が実現できます。

## 分散トレーシングの考え方
ここからは、 OpenTelemetry で分散トレーシングを実現する方法を知る前に、分散トレーシングの基本的な考え方について説明します。

以下の図は、 OpenTelemetry の公式サイトから引用した [分散トレーシングの概念図](https://opentelemetry.io/docs/concepts/observability-primer/#distributed-traces) です。 x 方向が時間を表し、 y 方向はサービスの階層構造を表していると考えてください。
![OpenTelemetry Trace](/images/OpenTelemetry_trace.png)

**トレースの構成要素**
トレースは、スパンと呼ばれる単位（上記の図における各ボックス）でサービス間やプロセス間のリクエストの流れを追跡し、スパンを繋ぎ合わせることで、リクエスト全体の流れを可視化します。

上記の図を注目すると：
- `client` というスパンは、クライアントがリクエストをしてからレスポンスを受け取るまでの一連の処理を表しています。
-  `/api` というスパンは、 API サービスにおける一連の処理を表しています。
- `/authN` や `/authZ` というスパンは、認証や認可の処理を表しています。

というように、各スパンは各サービスごとに生成される処理を表しています。そして、下の段に進むに連れて内部処理がブレイクダウンされています。

**ボトルネックの特定**
ここでブレイクダウンされた各スパンの大きさが、処理にかかった時間を表しています。このように、スパンの大きさを視覚的に比較することで、どのサービスや処理がボトルネックになっているかを特定することができます。

**エラーの特定**
また、特定の処理でエラーが発生した場合、 APM (Application Performance Management) ツールによって異なりますが、例えばスパンを表すボックスが赤くハイライトされたりして、ユーザーにエラーが発生したことを示すこともあります。

このようにして可視化することで、リクエストの流れを追跡し、ボトルネックやエラーの原因を特定することができます。

**各スパンが持つ情報**
スパンはサービスにおける処理の単位で生成され、基本的には以下のようなプロパティを持ちます。
| プロパティ      | 説明                                                                                   |
|----------------|----------------------------------------------------------------------------------------|
| トレース ID     | リクエスト全体を識別するための一意識別子                                               |
| スパン ID       | 個々のスパンを識別するための一意識別子                                                 |
| 親スパン ID     | 呼出し元のスパンを識別するための一意識別子（ルートのスパンの場合は存在しない）           |
| サービス名     | 処理が実行されたサービスの名前                                                         |
| スパン名       | 処理の名前                                                                             |
| 開始時刻       | 処理が開始された時刻                                                                   |
| 終了時刻       | 処理が終了した時刻                                                                     |

スパンはその他にも様々なプロパティ（例：属性、イベント、エラー情報など）を持つことができます。
詳しく知りたい方は、 OpenTelemetry のドキュメントで紹介されているため、以下のリンクを参照してみてください。
https://opentelemetry.io/ja/docs/concepts/observability-primer/#%e3%82%b9%e3%83%91%e3%83%b3%e5%b1%9e%e6%80%a7
https://opentelemetry.io/ja/docs/concepts/signals/traces/#spans


ここで、スパンを繋ぎ合わせてトレースを構成する上で重要になるプロパティは、トレース ID 、スパン ID 、親スパン ID です。各スパンが共通のトレース ID を持つことで一つのリクエストを構成する要素であることがわかります。また、各スパンが親スパン ID を持つことで、サービス間通信、プロセス間通信の呼び出し関係を表現することができます。

**トレース ID 、親スパン ID の引き継ぎ**
トレース ID や親スパン ID は、 HTTP ヘッダーや gRPC メタデータなどのリクエストのメタデータに含まれ、サービス間通信、プロセス間通信の際に次のサービスに伝播されます。
OpenTelemetry によって生成されるトレース ID やスパン ID 、それらを挿入するヘッダーやメタデータの形式は、 標準化を推進する団体である [W3C](https://www.w3.org/) によって定義された [W3C Trace Context](https://www.w3.org/TR/trace-context/) という仕様に準拠しています。[^2]
こうしたプロセスやネットワークの通信の中で、サービス間またはプロセス間でシステムに関する情報を伝播することを「コンテキスト伝播」と呼びます。
詳しく知りたい方は、 OpenTelemetry のドキュメントで紹介されているため、以下のリンクを参照してみてください。
https://opentelemetry.io/ja/docs/concepts/context-propagation/

このようにして、トレースはサービス間やプロセス間のリクエストの流れを追跡し、ボトルネックやエラーの原因が「どこのサービス」における「どの処理」で発生したのかを特定することに役立ちます。

## OpenTelemetry の導入
こうした分散トレーシングを実現するために、 OpenTelemetry が使用できます。
OpenTelemetry を導入するにあたり、以下の前提知識を紹介します。
- 計装（ Instrumentation ）の種類
- OpenTelemetry Protocol （ OTLP ）
- Collector の配置パターン

**計装（ Instrumentation ）の種類**
計装とは、アプリケーションに テレメトリーデータを収集、送信するための仕組みを組み込むことを指します。
計装には、手動計装と自動計装の 2 つの方法があります。

- 手動計装 : 開発者自身でアプリケーションコードに OpenTelemetry のライブラリを組み込み、テレメトリーデータを収集するためのコードを追加することを指します。 自分でコードを追加することで、特定のビジネスロジックや重要な処理のトレースをカスタマイズして収集することができます。
- 自動計装 : 開発者自身でアプリケーションコードに手を加えずにテレメトリーデータを収集する方法で、アプリケーションが使用するライブラリやフレームワークが OpenTelemetry が対応するものであれば、この方法を使用することができます。  

計装についても OpenTelemetry のドキュメントで紹介されているため、以下のリンクを参照してみてください。
https://opentelemetry.io/ja/docs/concepts/instrumentation/

**OTLP**
OTLP は、 HTTP や gRPC を使用した [OpenTelemetry のトレースデータを送信するための Wire Protocol](https://github.com/open-telemetry/opentelemetry-proto/blob/main/docs/design-goals.md) です。
そのため、 OpenTelemetry によって収集されたトレースを受信するためには、受信側コンポーネントが OTLP に対応している必要があります。
利用を検討している受信側コンポーネントが OTLP に対応しているかどうかを確認することが重要です。

他にも、直接的に受信コンポーネントにテレメトリーデータを送信せずに、 OpenTelemetry の Exporter や OpenTelemetry Collector などの中継コンポーネントへ送信することもできます。
この場合も、中継コンポーネントが OTLP に対応している必要があります。

OTLP に対応した受信側コンポーネントは OTLP エンドポイントを持ち、この OTLP エンドポイントを送信側のエクスポータに指定することで、トレースの送受信が可能になります。

OTLP の詳細な仕様については、以下のリンクを参照してください。
https://github.com/open-telemetry/opentelemetry-proto/tree/main/docs

**Collector の配置パターン**
Collector とは、 OpenTelemetry のデータを収集、処理、送信するためのコンポーネントです。
この Collector を配置する方法には、以下の 3 つのパターンがあります。
1. [No Collector](https://opentelemetry.io/ja/docs/collector/deployment/no-collector/) ：アプリケーションに直接 OpenTelemetry のライブラリを組み込み、アプリケーションから直接 OTLP エンドポイントにトレースを送信する方式
2. [Agent](https://opentelemetry.io/ja/docs/collector/deployment/agent/) ：同じホストやポッド上でサイドカー的にアプリケーションとは別のプロセスとして Collector を配置し、アプリケーションから Collector にトレースを送信する方式
3. [Gateway](https://opentelemetry.io/ja/docs/collector/deployment/gateway/) ：複数のアプリケーションからのテレメトリーデータを集約し、エクスポータに送信する方式

![alt text](/images/opentelemetry_no_collector.png =400x)
*No Collector*

![alt text](/images/opentelemetry_agent.png =900x)
*Agent*

![alt text](/images/opentelemetry_gateway.png =1500x)
*Gateway*

# ACA に OpenTelemetry を導入する
**Azure 上で実行されるアプリケーションに OpenTelemetry を導入する**
Azure 上で稼働するアプリケーションに OpenTelemetry を導入する場合、アプリケーションをホストする Azure サービスとアプリケーションの言語によって計装方法が異なります。

自動計装の対応状況については、以下のドキュメントに示されています。
https://learn.microsoft.com/ja-jp/azure/azure-monitor/app/codeless-overview#supported-environments-languages-and-resource-providers

以下の図は、執筆時点で上記のドキュメントから抜粋した表になります。見ての通り、 ACA では、現時点で自動計装はサポートされていません。
![alt text](/images/azure_application_insights/auto_instrumentation_support_table.png)

そして、手動計装の対応状況については、以下のドキュメントに示されています。執筆時点では、 .NET 、 ASP .NET Core 、 Java 、 Python 、 Node.js の言語が手動計装に対応しています。
![alt text](/images/azure_application_insights/manual_instrumentation_support_language.png)
*OpenTelemetry Distro を使用した手動計装に対応した言語*

https://learn.microsoft.com/ja-jp/azure/azure-monitor/app/app-insights-overview#manual-instrumentation

OpenTelemetry を手動計装して、 Application Insights にテレメトリーデータを送信する場合、 Microsoft が提供する OpenTelemetry のライブラリ [Azure Monitor OpenTelemetry Distro](https://learn.microsoft.com/ja-jp/azure/azure-monitor/app/opentelemetry-enable?tabs=aspnetcore) を使用することが推奨されています。（他にも Application Insights SDK が使用できますが、現在はクラシック API という位置づけで新規導入には推奨されていません）
<!-- AzMon Otel Distroについて解説 -->
Azure Monitor OpenTelemetry Distro は、 OpenTelemetry を使用して Azure Monitor にテレメトリーデータを送信するための特別なエクスポータを提供します。

## ACA に Azure Monitor OpenTelemetry Distro を導入する
ここからは、 ACA に OpenTelemetry を導入するための具体的な手順を説明します。

**デモシナリオについて**
本記事では、以下の図のような構成でアプリケーションを実行して、分散トレーシングを試してみましょう。
アプリケーションの処理はシンプルで、 ACA 上で稼働する 3 つのコンテナ間で JSON を伝播させていき、最終的に Azure Storage に保存する、というシナリオです。各コンテナアプリと Storage Account は同期的に通信します。つまり、 checkout のラウンドトリップには、後続の order-processor や receipt 、 Storage Account の処理時間も含まれます。
![alt text](/images/aca_otel_tracing_demo.png)

また、各コンテナアプリに対して OpenTelemetry が以下の条件で計装されており、テレメトリーデータが生成されます。
生成したテレメトリーデータは Azure Monitor に送信されて Application Insights 上で可視化することができます。（図からは省略していますが、実際の保存先としては Log Analytics Workspace が使用されます。）


- 計装 : 手動計装（ Azure Monitor OpenTelemetry Distro を使用）
- Collector の配置パターン : No Collector

**サンプルリポジトリの紹介**
上記のシナリオを実現するために、以下のサンプルリポジトリを用意しました。この後のセクションでは、このリポジトリを使用して 上記のシナリオを実際に試してみます。 Star をつけてもらえると励みになります⭐
https://github.com/Be3751/aca-otel-tracing

本リポジトリでは、以下の記事を参考にさせていただき、 OpenTelemetry のみを使用した分散トレーシングに変更し、 azd を使用して 簡単にデプロイできるようにしました。こちらの記事では、 ACA に Dapr と Application Insights を使用した分散トレーシングの導入方法について詳しく説明されています。
https://qiita.com/YoshiakiOi/items/9b8a64505daac8528418#%E4%B8%8A%E8%A8%98%E3%82%B3%E3%83%BC%E3%83%89%E3%81%AE-application-insights-%E5%88%A9%E7%94%A8%E6%99%82%E3%81%AE%E3%83%9D%E3%82%A4%E3%83%B3%E3%83%88

**Azure Monitor OpenTelemetry Distro を使用した手動計装**
ここからはサンプルリポジトリを紐解くような形で、 Azure Monitor OpenTelemetry Distro を使用した手動計装の方法を説明します。

基本的な計装の流れを説明します。
1. Azure Monitor OpenTelemetry Distro をアプリケーションに組み込む
2. アプリケーションの起動時に OpenTelemetry の初期化を行う
3. アプリケーションの処理ごとにスパンを開始し、
    - スパンの属性を設定する
    - スパンの終了時に、スパンを送信する
4. アプリケーションの終了時に OpenTelemetry のクリーンアップを行う

各アプリケーションは Python で実装されています。 Python では、以下のパッケージが Azure Monitor OpenTelemetry Distro を使用するために必要なパッケージです。 `pip install azure-monitor-opentelemetry` を実行するか、 [requirements.txt](https://github.com/Be3751/aca-otel-tracing/blob/main/apps/checkout/requirements.txt) に以下のパッケージを追加してインストールしてください。

https://pypi.org/project/azure-monitor-opentelemetry/


次に、環境変数を設定しています。各アプリケーションに共通して設定する環境変数は以下です。
| 環境変数名 | 説明 |
|-------------|----------------|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Application Insights の接続文字列。 Azure Monitor OpenTelemetry Distro のセットアップ用の関数の呼び出し時に使用されます。他の言語のセットアップ方法は [こちら](https://learn.microsoft.com/ja-jp/azure/azure-monitor/app/opentelemetry-configuration?tabs=python#connection-string) を参照してください。 |
| `OTEL_SERVICE_NAME` | アプリケーションのサービス名。ここで指定した名前が Application Insights におけるアプリケーションマップでトポロジー上のノードとして表示されます。詳細は [こちら](https://learn.microsoft.com/ja-jp/azure/azure-monitor/app/opentelemetry-configuration?tabs=python#set-the-cloud-role-name-and-the-cloud-role-instance) を参照してください。 |


本リポジトリでは、以下のように Bicep を使用して、 ACA 上にデプロイするコンテナアプリの環境変数を設定しています。以下は checkout コンテナアプリの Bicep モジュールです。各コンテナアプリの Bicep モジュールは [こちら](https://github.com/Be3751/aca-otel-tracing/tree/main/infra/app) で確認できます。
```bicep: infra/app/checkout-worker.bicep
module app '../core/host/container-app-worker.bicep' = {
  name: '${serviceName}-container-app-module'
  params: {
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': '${serviceName}-worker' })
    containerAppsEnvironmentName: containerAppsEnvironmentName
    containerRegistryName: containerRegistryName
    imageName: !empty(imageName) ? imageName : 'nginx:latest'
    containerName: serviceName
    managedIdentityEnabled: managedIdentityName != ''? true: false
    managedIdentityName: managedIdentityName
    env: [
      {
        name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
        value: applicationInsightsConnectionString
      }
      {
        name: 'OTEL_SERVICE_NAME'
        value: serviceName
      }
      {
        name: 'OTLP_EXPORT_ENDPOINT'
        value: 'http://tempo.monitoring.svc.cluster.local:3100'
      }
      {
        name: 'SERVICE_ORDER_PROCESSOR_API_NAME'
        value: orderProcessorApiName
      }
    ]
  }
}
```

そして、各コンテナで実行するアプリケーションコード内で Azure Monitor OpenTelemetry Distro を初期化していきます。さきほど解説した環境変数 `APPLICATIONINSIGHTS_CONNECTION_STRING` を使用して、 `configure_azure_monitor` 関数を呼び出します。本来は OTLP で通信するためのエンドポイントを指定する必要がありますが、 現状 Azure Monitor OpenTelemetry Distro では、 Application Insights の接続文字列を使用して自動的にエンドポイントを設定します。
```python: apps/checkout/app.py
connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

configure_azure_monitor(
  connection_string=connection_string
)
```

その他の Python の計装例は公式ドキュメントに Cookbook としてまとめられているので、詳しく知りたい方はこちらもご参照ください。 Python だけでなく他の言語の計装例もあります。
https://opentelemetry.io/docs/languages/python/cookbook/

また、 Azure Monitor OpenTelemetry Distro の計装例は、以下のリンクから各言語ごとに確認できます。
| 言語   | 計装例リンク                                                                 |
|--------|------------------------------------------------------------------------------|
| Python | https://github.com/Azure/azure-sdk-for-python/tree/main/sdk/monitor/azure-monitor-opentelemetry/samples                   |
| Java   | https://github.com/Azure-Samples/ApplicationInsights-Java-Samples                     |
| Java GraalVM | https://github.com/Azure-Samples/java-native-telemetry           |
| Node.js | https://github.com/Azure-Samples/azure-monitor-opentelemetry-node.js           |
| ASP.NET Core | https://github.com/Azure/azure-sdk-for-net/tree/main/sdk/monitor/Azure.Monitor.OpenTelemetry.AspNetCore/tests/Azure.Monitor.OpenTelemetry.AspNetCore.Demo           |
| .NET | https://github.com/Azure/azure-sdk-for-net/tree/main/sdk/monitor/Azure.Monitor.OpenTelemetry.Exporter/tests/Azure.Monitor.OpenTelemetry.Exporter.Demo           |

## アプリケーションをデプロイして分散トレーシングを確認する
検証を始める前に、以下の準備を行ってください。
- Azure アカウントの作成
- 有効なサブスクリプションの作成
- Azure Developer CLI （ azd ）のインストール

**azd を使用したアプリケーションのデプロイ**

以下の手順でコマンドを実行してください。本サンプルリポジトリでは、 bicep と azd を使用して、今回のシナリオに必要な Azure リソースのプロビジョニングからアプリケーションのデプロイや環境変数の構成までを自動的に実行できる形になっています。
```bash
# リポジトリをクローン
git clone https://github.com/Be3751/aca-otel-tracing.git

# クローンしたリポジトリのルートディレクトリに移動
cd aca-otel-tracing

# azd コマンドを使用して Azure リソースのプロビジョニングとアプリケーションのデプロイを実行
azd up
```

アプリケーションのデプロイが成功すると、以下のような出力が得られるはずです。
```
Successfully deployed the application.
You can access the application at:
  https://aca-otel-tracing.azurecontainerapps.io
```

Azure Portal でプロビジョニングした Container Apps 環境を確認すると、以下のように Container Apps 環境上にデプロイされた 3 つの Container App が実行されていることが分かります。
![alt text](/images/azure_container_apps_apps_on_environment.png)

それでは次に、分散トレーシングの結果を Application Insights で確認してみましょう。
以下の画像は作成された Application Insights の概要ページです。赤枠で囲った箇所が、今回使用するアプリケーションマップとトランザクションの検索です。
![alt text](/images/azure_application_insights/marked_application_map_and_transaction_search.png)

**アプリケーションマップ**

まずはアプリケーションマップを選択して表示してみましょう。
以下の画像は、今回デプロイしたアプリケーションのアプリケーションマップです。
![alt text](/images/azure_application_insights/application_map.png)

このアプリケーションマップに注目すると、以下のことが分かります。
| 注目箇所           | 意味                                                                 | 表示内容                                                                                      |
|--------------------|----------------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| ノードとエッジの繋がり   | システム全体の通信経路                                    | checkout → order-processor → receipt → Storage Account の順に通信                                       |
| ノードの枠線        | 各コンポーネントの実行ステータス                          | 全てのコンポーネントが正常動作（枠線が緑）                                        |
| ノード下のラベル    | 各ノードのサービス名や役割を明示                                     | checkout, order-processor, receipt, Storage Account などのサービス名がノード下に表示           |
| エッジ              | コンポーネント間のレイテンシ（平均）      | checkout → order-processor ： 105.6ms <br> order-processor → receipt ： 57.1ms <br> receipt → Storage Account ： 44.8ms <br> ※同期的に通信しているので、 checkout → order-processor のレイテンシには、 order-processor → receipt と receipt → Storage Account のレイテンシも含まれます。 |

:::message
アプリケーションマップではクラウド ロール名プロパティを使用して、マップ上のコンポーネントを識別します。そのため、各コンポーネントにクラウドロール名を設定できていない場合、コンポーネントが正しく識別されず、マップ上に表示されないことがある点に注意してください。クラウドロール名の設定方法は、言語によって異なりますが、 Python では 環境変数 `OTEL_SERVICE_NAME` にクラウドロール名を設定しました。詳しくは、以下のドキュメントを参照してください。
https://learn.microsoft.com/ja-jp/azure/azure-monitor/app/opentelemetry-configuration?tabs=python#set-the-cloud-role-name-and-the-cloud-role-instance
:::

今回は簡単に通信するだけのアプリケーションなので特にパフォーマンス上のボトルネックはないですが、例えば order-processor のレイテンシが他のコンポーネントに比べて高く、 receipt のレイテンシは低い場合、 order-processor の処理がボトルネックになっているとして調査を進めることができます。

また、もし一部のコンポーネントで異常が発生している場合は、コンポーネントの枠線が赤色になります。以下の画像は、 Azure Storage Account へのパブリックアクセスを無効にしてみて、 receipt コンテナアプリから Azure Storage Account への通信に異常が発生した場合のアプリケーションマップです。
![alt text](/images/azure_application_insights/application_map_error.png)

**トランザクションの検索**

次にトランザクションの検索を選択して表示してみましょう。
以下の画像は、今回デプロイしたアプリケーションのトランザクションの検索結果です。トランザクションの検索では、各スパンを時系列に従って繋ぎ合わせたトレースをウォーターフォール形式で表示します。
![alt text](/images/azure_application_insights/transaction_search.png)
アプリケーションマップではレイテンシがコンポーネント内で数値だけ表示されていたのに対し、トランザクションの検索ではスパンの長さによって、各スパンの処理時間を視覚的に確認できます。今回のデモアプリでは全てが同期的な通信をしているので、ルートである checkout コンテナアプリのスパンに後続のコンテナアプリや Storage Account のスパンがネストされて表示されている点が分かりやすく可視化されています。

また、スパンをクリックすることで、画面右側にサイドペインが表示されて、各スパンの詳細情報を確認できます。以下の画像は、 checkout コンテナアプリのスパンをクリックしたときの詳細情報です。スパンの開始時刻や実行時間、スパン名などの情報が表示されます。
![alt text](/images/azure_application_insights/transaction_search_detail.png)

特に注目したいプロパティは以下です。これらのプロパティによりスパン間の階層構造が Application Insights 上で再現され、トレース全体の流れを把握することができます。
- Id: スパンの一意識別子
- Parent Id: 親スパンの一意識別子
- Operation Id: トレースの一意識別子


実際に各スパンの Id 、 Parent Id 、 Operation Id を確認してみると、 checkout スパンの Id が order-processor スパンの Parent Id と一致していることが分かります。また、 Operation Id は異なるコンポーネントの両者で同じ値になっており、これらのスパンが同じトレースに属していることがわかります。ルートから 2 つ目のスパンまでを確認してみましたが、さらに下のスパンも同様に確認していくと、 receipt コンテナアプリのスパンの Parent Id が order-processor コンテナアプリのスパンの Id と一致しています。
![alt text](/images/azure_application_insights/span_detail_parent.png)
*checkout コンテナアプリのスパン詳細*

![alt text](/images/azure_application_insights/span_detail_child.png)
*order-processor コンテナアプリのスパン詳細*

このようにスパンを構造化するための Id 付与が分散トレーシングの重要な点の一つですが、こうした Id の付与は Azure Monitor OpenTelemetry Distro を導入することで自動的に行われます。

もしも、一部のコンポーネントで異常が発生している場合は、トランザクションの検索結果でもエラーが発生したスパンが赤色でハイライトされます。以下の画像は、先ほどのアプリケーションマップで receipt コンテナアプリから Azure Storage Account への通信に異常が発生した場合のトランザクションの検索結果です。
![alt text](/images/azure_application_insights/transaction_search_error.png)

また、詳細画面の下部に進むと「コールスタック」というセクションがあり、エラーが発生した場合は、エラーのスタックトレースを確認することができます。以下の画像は、 receipt コンテナアプリの order スパンの詳細画面で、エラーのスタックトレースを表示したものです。このように構造化されたスパンとそれらに関連付けられたログを確認することで、どういった通信経路でどんなエラーが発生したのかを特定することができます。
![alt text](/images/azure_application_insights/transaction_search_error_stack_trace.png)

以上が、 Application Insights を使用した分散トレーシングの基本的な方法です。特にマイクロサービスが十数個、数十個あるような構成のシステムでは、アプリケーションマップやトランザクションの検索を活用して、システムの内部状況を可視化し、ボトルネックやエラーの原因を効率的に特定することに役立てられます。

# まとめ
本記事では、分散トレーシングや OpenTelemetry の基本的な考え方を紹介し、 Azure Container Apps 上で OpenTelemetry を導入して分散トレーシングを実現する方法を説明しました。

今回は、 Azure Monitor OpenTelemetry Distro を使用して、 ACA 上で稼働するアプリケーションに手動計装を行うパターンを紹介しましたが、 ACA では Dapr を使用した分散トレーシングの導入や OpenTelemetry エージェントを使用した Agent の配置パターンも可能です。
こうした他のパターンについては、次回以降の記事で紹介できればと思います。

今後は、このリポジトリに ACA と OpenTelemetry を使用した分散トレーシングのサンプルコードを他にも追加していこうと考えています。
https://github.com/Be3751/aca-otel-tracing

この内容を通じて、 ACA における OpenTelemetry の導入方法を理解し、分散トレーシングを活用する手助けになれば幸いです。

[^1]: OpenTelemetry の主な目的は、あなたのアプリケーションやシステムを、その言語、インフラ、ランタイム環境に関係なく、簡単に計装できるようにすることです。テレメトリーデータのバックエンド（保存）とフロントエンド（可視化）は意図的に他のツールに任せています。（ https://opentelemetry.io/ja/docs/what-is-opentelemetry/ より抜粋）

[^2]: The OpenTelemetry SpanContext representation conforms to the W3C TraceContext specification. It contains two identifiers - a TraceId and a SpanId - along with a set of common TraceFlags and system-specific TraceState values. （ https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/trace/api.md より抜粋）