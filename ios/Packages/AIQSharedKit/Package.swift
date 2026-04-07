// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AIQSharedKit",
    platforms: [
        .iOS(.v16)
    ],
    products: [
        .library(
            name: "AIQSharedKit",
            targets: ["AIQSharedKit"]
        ),
        .library(
            name: "AIQOfflineQueue",
            targets: ["AIQOfflineQueue"]
        )
    ],
    dependencies: [
        .package(
            url: "https://github.com/gioe/ios-libs",
            from: "1.4.0"
        )
    ],
    targets: [
        .target(
            name: "AIQSharedKit",
            dependencies: [],
            swiftSettings: [
                .define("DebugBuild", .when(configuration: .debug))
            ]
        ),
        .target(
            name: "AIQOfflineQueue",
            dependencies: [
                .product(name: "SharedKit", package: "ios-libs")
            ]
        ),
        .testTarget(
            name: "AIQSharedKitTests",
            dependencies: ["AIQSharedKit"],
            swiftSettings: [
                .define("DebugBuild", .when(configuration: .debug))
            ]
        )
    ]
)
