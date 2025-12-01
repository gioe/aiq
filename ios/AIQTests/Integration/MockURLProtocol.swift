import Foundation

/// Mock URLProtocol for integration testing
class MockURLProtocol: URLProtocol {
    static var requestHandler: ((URLRequest) throws -> (HTTPURLResponse, Data))?

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
        guard let handler = MockURLProtocol.requestHandler else {
            fatalError("Request handler is not set")
        }

        do {
            // Restore httpBody from property storage if needed
            var requestToHandle = request
            if requestToHandle.httpBody == nil,
               let savedBody = URLProtocol.property(forKey: Self.httpBodyKey, in: request) as? Data {
                var mutableRequest = request
                mutableRequest.httpBody = savedBody
                requestToHandle = mutableRequest
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
