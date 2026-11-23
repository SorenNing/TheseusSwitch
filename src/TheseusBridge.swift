import UIKit

// No geometry, material, animation, colour or physics override is applied to
// this instance. Only the existing UISwitch's value and enabled state are bound.
@objc(NGTheseusSwitch)
final class NGTheseusSwitch: UIView {
    private let toggle = TheseusSwitch()
    @objc var onChanged: ((Bool) -> Void)?
    @objc var on: Bool {
        get { toggle.isOn }
        set { toggle.isOn = newValue }
    }
    @objc(isOn) func isOn() -> Bool { toggle.isOn }

    override init(frame: CGRect) {
        super.init(frame: CGRect(origin: frame.origin, size: CGSize(width: 63, height: 28)))
        backgroundColor = .clear
        clipsToBounds = false
        isOpaque = false
        addSubview(toggle)
        toggle.frame = bounds
        toggle.onValueChanged = { [weak self] value in self?.onChanged?(value) }
    }
    required init?(coder: NSCoder) { return nil }
    override var intrinsicContentSize: CGSize { toggle.intrinsicContentSize }
    override func layoutSubviews() { super.layoutSubviews(); toggle.frame = bounds }
    @objc(setOn:animated:) func setOn(_ value: Bool, animated: Bool) {
        toggle.setOn(value, animated: animated)
    }
    @objc(setControlEnabled:) func setControlEnabled(_ enabled: Bool) { toggle.isEnabled = enabled }
    override var accessibilityLabel: String? {
        get { toggle.accessibilityLabel }
        set { toggle.accessibilityLabel = newValue }
    }
    override func accessibilityActivate() -> Bool { toggle.accessibilityActivate() }
}
