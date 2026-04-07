import AIQSharedKit
import Combine
import Foundation

/// Re-export SharedKit's BaseViewModel for the AIQ app.
/// All ViewModels in the AIQ app inherit from this typealias,
/// which resolves to AIQSharedKit.BaseViewModel.
typealias BaseViewModel = AIQSharedKit.BaseViewModel
