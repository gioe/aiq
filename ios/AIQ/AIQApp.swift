import SwiftUI

@main
struct AIQApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var router = AppRouter()
    @Environment(\.scenePhase) private var scenePhase

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
        .onChange(of: scenePhase) { newPhase in
            // Schedule background refresh when app moves to background
            if newPhase == .background {
                Task { @MainActor in
                    BackgroundRefreshManager.shared.scheduleRefresh()
                }
            }
        }
    }
}
