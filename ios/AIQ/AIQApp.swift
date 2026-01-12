import SwiftUI

@main
struct AIQApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var router = AppRouter()

    init() {
        // Configure dependency injection container during app initialization
        ServiceConfiguration.configureServices(container: ServiceContainer.shared)
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .withAppRouter(router)
                .environment(\.serviceContainer, ServiceContainer.shared)
        }
    }
}
