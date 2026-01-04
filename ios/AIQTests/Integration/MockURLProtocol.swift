import Foundation

/// Mock URLProtocol for integration testing
class MockURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

    /// Default handler that returns a generic success response when no specific handler is set.
    /// This prevents test crashes when unexpected network requests occur (e.g., auto-batch submission).
    private static let defaultHandler: (URLRequest) throws -> (HTTPURLResponse, Data) = { request in
        let response = HTTPURLResponse(
            url: request.url ?? URL(string: "https://mock.test")!,
            statusCode: 200,
            httpVersion: nil,
            headerFields: nil
        )!
        let data = """
        {"success": true, "message": "Default mock response"}
        """.data(using: .utf8)!
        return (response, data)
    }

    // Store httpBody in a property key to preserve it across the request lifecycle
    private static let httpBodyKey = "MockURLProtocol.httpBody"

    override class func canInit(with _: URLRequest) -> Bool {
        true
    }

    override class func canonicalRequest(for request: URLRequest) -> URLRequest {
        // Preserve the httpBody by storing it in URLProtocol's property storage
        guard let mutableRequest = (request as NSURLRequest).mutableCopy() as? NSMutableURLRequest else {
            return request
        }

        if let body = request.httpBody, URLProtocol.property(forKey: httpBodyKey, in: request) == nil {
            URLProtocol.setProperty(body, forKey: httpBodyKey, in: mutableRequest)
        }

        return mutableRequest as URLRequest
    }

    override func startLoading() {
        // Use provided handler or default to a generic success response
        let handler = MockURLProtocol.requestHandler ?? Self.defaultHandler

        do {
            // Restore httpBody from property storage, httpBody, or httpBodyStream
            var requestToHandle = request
            if let savedBody = URLProtocol.property(forKey: Self.httpBodyKey, in: request) as? Data {
                // Body was saved in canonicalRequest
                guard let mutableRequest = (request as NSURLRequest).mutableCopy() as? NSMutableURLRequest else {
                    fatalError("Failed to create mutable copy of request")
                }
                mutableRequest.httpBody = savedBody
                requestToHandle = mutableRequest as URLRequest
            } else if request.httpBody == nil, let bodyStream = request.httpBodyStream {
                // Read from body stream if no httpBody is present
                bodyStream.open()
                let bufferSize = 1024
                var data = Data()
                let buffer = UnsafeMutablePointer<UInt8>.allocate(capacity: bufferSize)
                defer { buffer.deallocate() }

                while bodyStream.hasBytesAvailable {
                    let bytesRead = bodyStream.read(buffer, maxLength: bufferSize)
                    if bytesRead > 0 {
                        data.append(buffer, count: bytesRead)
                    }
                }
                bodyStream.close()

                guard let mutableRequest = (request as NSURLRequest).mutableCopy() as? NSMutableURLRequest else {
                    fatalError("Failed to create mutable copy of request")
                }
                mutableRequest.httpBody = data
                requestToHandle = mutableRequest as URLRequest
            }

            let (response, data) = try handler(requestToHandle)
            client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
            client?.urlProtocol(self, didLoad: data)
            client?.urlProtocolDidFinishLoading(self)
        } catch {
            client?.urlProtocol(self, didFailWithError: error)
        }
    }

    override func stopLoading() {
        // Nothing to do
    }
}
