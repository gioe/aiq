import Combine
import Foundation
import SharedKit

/// Re-export SharedKit's BaseViewModel for the AIQ app.
/// All ViewModels in the AIQ app inherit from this typealias,
/// which resolves to SharedKit.BaseViewModel.
typealias BaseViewModel = SharedKit.BaseViewModel
