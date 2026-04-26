import AuthenticationServices
import CryptoKit
import Foundation
import Security

struct AppleSignInNonceContext {
    private(set) var rawNonce: String?

    mutating func prepare(_ request: ASAuthorizationAppleIDRequest) {
        let nonce = Self.makeNonce()
        rawNonce = nonce
        request.requestedScopes = [.email]
        request.nonce = Self.sha256(nonce)
    }

    mutating func consumeRawNonce() -> String? {
        defer { rawNonce = nil }
        return rawNonce
    }

    mutating func clear() {
        rawNonce = nil
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

            for random in randomBytes where remainingLength > 0 {
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
