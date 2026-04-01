// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "APIClient",
    platforms: [
        .iOS(.v16),
        .macOS(.v13)
    ],
    products: [
        .library(
            name: "APIClient",
            targets: ["APIClient"]
        ),
        .library(
            name: "AIQAPIClient",
            targets: ["AIQAPIClient"]
        )
    ],
    dependencies: [
        .package(
            url: "https://github.com/apple/swift-openapi-generator",
            from: "1.10.4"
        ),
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
        )
    ],
    targets: [
        .target(
            name: "APIClient",
            dependencies: [
                .product(name: "OpenAPIRuntime", package: "swift-openapi-runtime"),
                .product(name: "OpenAPIURLSession", package: "swift-openapi-urlsession"),
                .product(name: "HTTPTypes", package: "swift-http-types")
            ],
            swiftSettings: [
                .define("DebugBuild", .when(configuration: .debug))
            ],
            plugins: [
                .plugin(name: "OpenAPIGenerator", package: "swift-openapi-generator")
            ]
        ),
        .target(
            name: "AIQAPIClient",
            dependencies: [
                "APIClient"
            ]
        ),
        .testTarget(
            name: "APIClientTests",
            dependencies: [
                "APIClient",
                .product(name: "OpenAPIRuntime", package: "swift-openapi-runtime"),
                .product(name: "HTTPTypes", package: "swift-http-types")
            ],
            path: "Tests/APIClientTests"
        )
    ]
)
