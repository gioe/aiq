// AIQAPIClient — product-specific UIKit/SwiftUI extensions on generated OpenAPI types.
//
// This target provides a home for AIQ-specific UI computed properties on top of the
// generated `APIClient` types. Extensions here follow the "bring-your-own-extensions"
// pattern: the core `APIClient` target stays product-agnostic, while this target adds
// AIQ UX decisions (formatting, accessibility labels, display helpers).
//
// The main AIQ app also defines extensions directly in `AIQ/Models/` via
// `<TypeName>+Extensions.swift` files. Use this target for extensions that belong
// to the API layer (e.g. schema-level display helpers) and `AIQ/Models/` for
// app-level domain logic.

import AIQAPIClientCore
import Foundation
