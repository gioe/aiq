// DebugFlags.swift
// Canonical definition of the DebugBuild compilation condition.
//
// DebugBuild is active whenever DEBUG is active. It is defined via:
//   - SWIFT_ACTIVE_COMPILATION_CONDITIONS = "DEBUG DebugBuild" (Xcode, main app + test targets)
//   - .define("DebugBuild", .when(configuration: .debug)) (Swift Package Manager targets)
//
// Use `#if DebugBuild` (not `#if DEBUG`) throughout the codebase to gate debug-only code.
// Use `BuildEnvironment.isDebug` for runtime boolean checks.

/// Provides a runtime boolean for the current build environment.
///
/// Use `BuildEnvironment.isDebug` to conditionally execute debug-only code paths at runtime.
/// For compile-time type exclusion (e.g., entire debug-only type definitions), use `#if DebugBuild`.
public enum BuildEnvironment {
    #if DebugBuild
        /// `true` in Debug builds, `false` in Release builds.
        ///
        /// Use this for runtime-conditional debug behavior. For compile-time type exclusion
        /// (e.g., entire debug-only type definitions), use `#if DebugBuild` directly.
        public static let isDebug = true
    #else
        /// `true` in Debug builds, `false` in Release builds.
        ///
        /// Use this for runtime-conditional debug behavior. For compile-time type exclusion
        /// (e.g., entire debug-only type definitions), use `#if DebugBuild` directly.
        public static let isDebug = false
    #endif
}
