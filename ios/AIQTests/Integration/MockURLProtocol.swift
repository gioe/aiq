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
            // Restore httpBody from property storage, httpBody, or httpBodyStream
            var requestToHandle = request
            if let savedBody = URLProtocol.property(forKey: Self.httpBodyKey, in: request) as? Data {
                // Body was saved in canonicalRequest
                var mutableRequest = (request as NSURLRequest).mutableCopy() as! NSMutableURLRequest
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

                var mutableRequest = (request as NSURLRequest).mutableCopy() as! NSMutableURLRequest
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
