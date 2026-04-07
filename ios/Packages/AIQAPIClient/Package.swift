// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AIQAPIClient",
    platforms: [
        .iOS(.v16),
        .macOS(.v13)
    ],
    products: [
        .library(
            name: "AIQAPIClientCore",
            targets: ["AIQAPIClientCore"]
        ),
        .library(
            name: "AIQAPIClient",
            targets: ["AIQAPIClient"]
        )
    ],
    dependencies: [
        .package(
            url: "https://github.com/apple/swift-openapi-runtime",
            from: "1.9.0"
        ),
        .package(
            url: "https://github.com/apple/swift-openapi-urlsession",
            from: "1.0.0"
        ),
        .package(
            url: "https://github.com/apple/swift-http-types",
            from: "1.0.0"
        ),
        .package(
            url: "https://github.com/gioe/ios-libs",
            from: "1.4.0"
        )
    ],
    targets: [
        .target(
            name: "AIQAPIClientCore",
            dependencies: [
                .product(name: "OpenAPIRuntime", package: "swift-openapi-runtime"),
                .product(name: "OpenAPIURLSession", package: "swift-openapi-urlsession"),
                .product(name: "HTTPTypes", package: "swift-http-types")
            ],
            exclude: [
                "openapi.json",
                "openapi-generator-config.yaml"
            ],
            swiftSettings: [
                .define("DebugBuild", .when(configuration: .debug))
            ]
        ),
        .target(
            name: "AIQAPIClient",
            dependencies: [
                "AIQAPIClientCore",
                .product(name: "APIClient", package: "ios-libs")
            ]
        ),
        .testTarget(
            name: "AIQAPIClientCoreTests",
            dependencies: [
                "AIQAPIClientCore",
                .product(name: "OpenAPIRuntime", package: "swift-openapi-runtime"),
                .product(name: "HTTPTypes", package: "swift-http-types")
            ],
            path: "Tests/AIQAPIClientCoreTests"
        )
    ]
)
