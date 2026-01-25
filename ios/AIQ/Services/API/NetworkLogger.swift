import Foundation

/// Logs network requests and responses for debugging
struct NetworkLogger {
    static let shared = NetworkLogger()

    private init() {}

    func logRequest(_ request: URLRequest) {
        #if DEBUG
            print("[REQUEST] \(request.httpMethod ?? "UNKNOWN") \(request.url?.absoluteString ?? "NO URL")")

            if let headers = request.allHTTPHeaderFields, !headers.isEmpty {
                print("  Headers:")
                for (key, value) in headers {
                    // Mask sensitive headers
                    if key.lowercased() == "authorization" {
                        print("    \(key): ***MASKED***")
                    } else {
                        print("    \(key): \(value)")
                    }
                }
            }

            if let body = request.httpBody,
               let jsonObject = try? JSONSerialization.jsonObject(with: body),
               let prettyData = try? JSONSerialization.data(withJSONObject: jsonObject, options: .prettyPrinted),
               let prettyString = String(data: prettyData, encoding: .utf8) {
                print("  Body:")
                print(prettyString)
            }
        #endif
    }

    func logResponse(_ response: HTTPURLResponse, data: Data?) {
        #if DEBUG
            let isSuccess = response.statusCode >= 200 && response.statusCode < 300
            let statusPrefix = isSuccess ? "[RESPONSE]" : "[RESPONSE ERROR]"
            print("\(statusPrefix) \(response.statusCode) \(response.url?.absoluteString ?? "NO URL")")

            if let data,
               let jsonObject = try? JSONSerialization.jsonObject(with: data),
               let prettyData = try? JSONSerialization.data(withJSONObject: jsonObject, options: .prettyPrinted),
               let prettyString = String(data: prettyData, encoding: .utf8) {
                print("  Body:")
                print(prettyString)
            }
        #endif
    }

    func logError(_ error: Error, for url: URL?) {
        #if DEBUG
            print("[ERROR] \(url?.absoluteString ?? "NO URL")")
            print("  \(error.localizedDescription)")
        #endif
    }
}
