// swift-tools-version: 6.2

import PackageDescription

let package = Package(
    name: "KarlController",
    platforms: [
        .macOS(.v15)
    ],
    products: [
        .executable(name: "KarlController", targets: ["KarlController"])
    ],
    targets: [
        .executableTarget(
            name: "KarlController",
            swiftSettings: [
                .defaultIsolation(MainActor.self)
            ]
        ),
        .testTarget(
            name: "KarlControllerTests",
            dependencies: ["KarlController"]
        )
    ]
)
