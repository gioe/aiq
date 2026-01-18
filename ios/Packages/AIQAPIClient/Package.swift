// swift-tools-version: 5.9
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "AIQAPIClient",
    platforms: [
        .iOS(.v16),
        .macOS(.v10_15)
    ],
    products: [
        // The generated OpenAPI client will be exported as a library
        .library(
            name: "AIQAPIClient",
            targets: ["AIQAPIClient"]
        )
    ],
    dependencies: [
        // Swift OpenAPI Generator - build tool plugin
        .package(
            url: "https://github.com/apple/swift-openapi-generator",
            from: "1.10.4"
        ),
        // Swift OpenAPI Runtime - runtime library for generated code
        .package(
            url: "https://github.com/apple/swift-openapi-runtime",
            from: "1.9.0"
        ),
        // URLSession transport for the OpenAPI client
        .package(
            url: "https://github.com/apple/swift-openapi-urlsession",
            from: "1.0.0"
        )
    ],
    targets: [
        .target(
            name: "AIQAPIClient",
            dependencies: [
                .product(name: "OpenAPIRuntime", package: "swift-openapi-runtime"),
                .product(name: "OpenAPIURLSession", package: "swift-openapi-urlsession")
            ],
            plugins: [
                // This plugin generates Swift code from the OpenAPI spec at build time
                .plugin(name: "OpenAPIGenerator", package: "swift-openapi-generator")
            ]
        )
    ]
)
