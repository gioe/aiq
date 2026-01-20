import SwiftUI

@main
struct AIQApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var router = AppRouter()
    @Environment(\.scenePhase) private var scenePhase

    init() {
        // Configure dependency injection container during app initialization
        // In DEBUG builds, check for UI test mock mode and use mock services if enabled
        #if DEBUG
            if MockModeDetector.isMockMode {
                // App.init() runs on the main thread, so we can assume main actor isolation
                // for calling the @MainActor mock configuration method
                MainActor.assumeIsolated {
                    MockServiceConfiguration.configureServices(container: ServiceContainer.shared)
                }
            } else {
                ServiceConfiguration.configureServices(container: ServiceContainer.shared)
            }
        #else
            ServiceConfiguration.configureServices(container: ServiceContainer.shared)
        #endif

        // Mark configuration complete to enable DEBUG assertions for late registrations
        ServiceContainer.shared.markConfigurationComplete()
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(router)
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
