import AIQSharedKit
import AuthenticationServices
import CryptoKit
import Security
import SwiftUI
import UIKit

struct OAuthSignInButtonIdentifiers {
    let apple: String
    let google: String
}

struct OAuthSignInButtonLabels {
    let apple: String
    let google: String
}

struct OAuthSignInButtons: View {
    enum Placement {
        case welcome
        case guestResults

        var identifiers: OAuthSignInButtonIdentifiers {
            switch self {
            case .welcome:
                OAuthSignInButtonIdentifiers(
                    apple: AccessibilityIdentifiers.WelcomeView.signInWithAppleButton,
                    google: AccessibilityIdentifiers.WelcomeView.signInWithGoogleButton
                )
            case .guestResults:
                OAuthSignInButtonIdentifiers(
                    apple: AccessibilityIdentifiers.GuestTestContainerView.signInWithAppleButton,
                    google: AccessibilityIdentifiers.GuestTestContainerView.signInWithGoogleButton
                )
            }
        }

        var labels: OAuthSignInButtonLabels {
            switch self {
            case .welcome:
                OAuthSignInButtonLabels(
                    apple: "Sign in with Apple",
                    google: "Sign in with Google"
                )
            case .guestResults:
                OAuthSignInButtonLabels(
                    apple: "Sign in with Apple",
                    google: "Continue with Google"
                )
            }
        }
    }

    let placement: Placement
    let isDisabled: Bool
    let onAppleRequest: (ASAuthorizationAppleIDRequest) -> Void
    let onAppleCompletion: (Result<ASAuthorization, Error>) -> Void
    let onGoogleSignIn: () -> Void

    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        let identifiers = placement.identifiers
        let labels = placement.labels

        VStack(spacing: DesignSystem.Spacing.md) {
            SignInWithAppleButton(
                onRequest: onAppleRequest,
                onCompletion: onAppleCompletion
            )
            .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
            .frame(height: 40)
            .cornerRadius(OAuthBrandButtonMetrics.cornerRadius)
            .disabled(isDisabled)
            .accessibilityIdentifier(identifiers.apple)
            .accessibilityLabel(labels.apple)

            GoogleBrandSignInButton(
                title: labels.google,
                scheme: colorScheme == .dark ? .dark : .light,
                action: onGoogleSignIn
            )
            .disabled(isDisabled)
            .accessibilityIdentifier(identifiers.google)
            .accessibilityLabel(labels.google)
        }
    }
}

private struct GoogleBrandSignInButton: View {
    enum Scheme {
        case light
        case dark
    }

    let title: String
    let scheme: Scheme
    let action: () -> Void

    @Environment(\.isEnabled) private var isEnabled

    private var fillColor: Color {
        switch scheme {
        case .light:
            Color(red: 1, green: 1, blue: 1)
        case .dark:
            Color(red: 0.0745, green: 0.0745, blue: 0.0784)
        }
    }

    private var strokeColor: Color {
        switch scheme {
        case .light:
            Color(red: 0.4549, green: 0.4667, blue: 0.4588)
        case .dark:
            Color(red: 0.5569, green: 0.5686, blue: 0.5608)
        }
    }

    private var titleColor: Color {
        switch scheme {
        case .light:
            Color(red: 0.1216, green: 0.1216, blue: 0.1216)
        case .dark:
            Color(red: 0.8902, green: 0.8902, blue: 0.8902)
        }
    }

    var body: some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image("GoogleGLogo")
                    .resizable()
                    .frame(width: 20, height: 20)
                    .accessibilityHidden(true)

                Text(title)
                    .font(.custom("Roboto-Medium", size: 14, relativeTo: .body))
                    .fontWeight(.medium)
                    .foregroundColor(titleColor)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .center)
            }
            .padding(.leading, 16)
            .padding(.trailing, 16)
            .frame(height: 40)
            .frame(maxWidth: .infinity)
            .background(fillColor)
            .overlay(
                RoundedRectangle(cornerRadius: OAuthBrandButtonMetrics.cornerRadius)
                    .stroke(strokeColor, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: OAuthBrandButtonMetrics.cornerRadius))
            .opacity(isEnabled ? 1 : 0.6)
        }
        .buttonStyle(.plain)
    }
}

private enum OAuthBrandButtonMetrics {
    static let height: CGFloat = 40
    static let cornerRadius: CGFloat = height / 2
}

enum OAuthSignInSupport {
    static func rootPresentingViewController() -> UIViewController? {
        UIApplication.shared.connectedScenes
            .compactMap { $0 as? UIWindowScene }
            .filter { $0.activationState == .foregroundActive }
            .flatMap(\.windows)
            .first(where: \.isKeyWindow)?
            .rootViewController
    }

    static func makeNonce(length: Int = 32) -> String {
        precondition(length > 0)

        let charset = Array("0123456789ABCDEFGHIJKLMNOPQRSTUVXYZabcdefghijklmnopqrstuvwxyz-._")
        var result = ""
        result.reserveCapacity(length)
        var remainingLength = length

        while remainingLength > 0 {
            var randomBytes = [UInt8](repeating: 0, count: 16)
            let status = SecRandomCopyBytes(kSecRandomDefault, randomBytes.count, &randomBytes)
            precondition(status == errSecSuccess, "Failed to generate secure random bytes")

            for random in randomBytes {
                if remainingLength == 0 {
                    break
                }

                if random < charset.count {
                    result.append(charset[Int(random)])
                    remainingLength -= 1
                }
            }
        }

        return result
    }

    static func sha256(_ input: String) -> String {
        let digest = SHA256.hash(data: Data(input.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }
}
