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
        .testTarget(
            name: "AIQSharedKitTests",
            dependencies: ["AIQSharedKit"],
            swiftSettings: [
                .define("DebugBuild", .when(configuration: .debug))
            ]
        )
    ]
)
