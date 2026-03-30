// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "SharedKit",
    platforms: [
        .iOS(.v16)
    ],
    products: [
        .library(
            name: "SharedKit",
            targets: ["SharedKit"]
        )
    ],
    targets: [
        .target(
            name: "SharedKit",
            dependencies: []
        )
    ]
)
