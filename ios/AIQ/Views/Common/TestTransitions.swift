import SwiftUI

// MARK: - Shared Test Transition Extensions

extension View {
    /// Fade + slight scale-down transition for loading/submitting overlays.
    func loadingOverlayTransition(reduceMotion: Bool) -> some View {
        transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.9)))
    }

    /// Asymmetric slide + fade transition for question cards (trailing in, leading out).
    func questionCardTransition(reduceMotion: Bool) -> some View {
        transition(reduceMotion ? .opacity : .asymmetric(
            insertion: .move(edge: .trailing).combined(with: .opacity),
            removal: .move(edge: .leading).combined(with: .opacity)
        ))
    }

    /// Fade + slight scale-down transition for answer input areas.
    func answerInputTransition(reduceMotion: Bool) -> some View {
        transition(reduceMotion ? .opacity : .opacity.combined(with: .scale(scale: 0.95)))
    }

    /// Slide-from-top + fade transition for banners and collapsible panels.
    func bannerSlideTransition(reduceMotion: Bool) -> some View {
        transition(reduceMotion ? .opacity : .move(edge: .top).combined(with: .opacity))
    }
}
