import AIQSharedKit
import AuthenticationServices
import CryptoKit
import GoogleSignInSwift
import Security
import SwiftUI
import UIKit

struct OAuthSignInButtonIdentifiers {
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
    }

    let placement: Placement
    let isDisabled: Bool
    let onAppleRequest: (ASAuthorizationAppleIDRequest) -> Void
    let onAppleCompletion: (Result<ASAuthorization, Error>) -> Void
    let onGoogleSignIn: () -> Void

    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        let identifiers = placement.identifiers

        VStack(spacing: DesignSystem.Spacing.md) {
            SignInWithAppleButton(
                onRequest: onAppleRequest,
                onCompletion: onAppleCompletion
            )
            .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
            .frame(height: 50)
            .cornerRadius(DesignSystem.CornerRadius.md)
            .disabled(isDisabled)
            .accessibilityIdentifier(identifiers.apple)

            GoogleSignInButton(
                scheme: colorScheme == .dark ? .dark : .light,
                style: .wide,
                action: onGoogleSignIn
            )
            .frame(height: 50)
            .disabled(isDisabled)
            .accessibilityIdentifier(identifiers.google)
        }
    }
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
