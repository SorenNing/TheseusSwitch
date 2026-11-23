import Foundation

extension Bundle {
    static var module: Bundle {
        guard let resources = NGBundleResources() else {
            preconditionFailure("TheseusSwitch resource bundle is missing")
        }
        return resources
    }
}
