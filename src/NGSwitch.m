#import "Bridge.h"
#import <objc/runtime.h>
#import <objc/message.h>

static char kNGBindingKey;

static UIView *NGSwitchOverlayHost(UISwitch *source) {
    UIView *host = source.superview;
    // Some settings cells clip their subviews to a narrow content column.  A
    // 63pt glass switch placed there is reduced to a visible edge only.  Move
    // the overlay to the first unclipped ancestor and convert coordinates into
    // that host's space.
    while (host && host != source.window) {
        UIView *superview = host.superview;
        if (!host.clipsToBounds && !(superview && superview.clipsToBounds)) break;
        host = superview;
    }
    return host ?: source.window ?: source.superview;
}

static NSHashTable<UISwitch *> *NGSeenSwitches(void) {
    static NSHashTable *seen; static dispatch_once_t once;
    dispatch_once(&once, ^{ seen = [NSHashTable weakObjectsHashTable]; }); return seen;
}

@interface NGSwitchBinding : NSObject
@property(nonatomic,weak) UISwitch *source;
@property(nonatomic,strong) UIView *overlay;
@property(nonatomic) CGFloat originalAlpha;
@property(nonatomic) BOOL originalAccessibility;
@property(nonatomic) BOOL forwarding;
@property(nonatomic) BOOL modifyingNative;
- (void)commit:(BOOL)value;
@end

@implementation NGSwitchBinding
- (void)dealloc { [_overlay removeFromSuperview]; }
- (void)commit:(BOOL)value {
    UISwitch *source = self.source;
    if (!source || !source.enabled || !source.userInteractionEnabled || self.forwarding || !NGSwitchEnabled() || self.overlay.hidden) return;
    if (source.isOn == value) return;
    self.forwarding = YES;
    @try { [source setOn:value animated:NO]; }
    @finally { self.forwarding = NO; }
    [source sendActionsForControlEvents:UIControlEventValueChanged];
    // A target may synchronously reject a value; mirror its actual final state.
    NGSyncSwitch(source, NO);
}
@end

void NGSyncSwitch(UISwitch *source, BOOL animated) {
    NGSwitchBinding *binding = objc_getAssociatedObject(source, &kNGBindingKey);
    if (!binding || binding.forwarding) return;
    id<NGSwitchComponent> component = (id)binding.overlay;
    if ([(id)component isOn] != source.isOn) [component setOn:source.isOn animated:animated];
    SEL enabled = NSSelectorFromString(@"setControlEnabled:");
    if ([binding.overlay respondsToSelector:enabled]) ((void(*)(id,SEL,BOOL))objc_msgSend)(binding.overlay,enabled,source.enabled);
    binding.overlay.accessibilityLabel = source.accessibilityLabel;
}

void NGRemoveSwitch(UISwitch *source) {
    NGSwitchBinding *binding = objc_getAssociatedObject(source,&kNGBindingKey);
    if (!binding) return;
    [binding.overlay removeFromSuperview];
    objc_setAssociatedObject(source,&kNGBindingKey,nil,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    source.alpha = binding.originalAlpha;
    source.isAccessibilityElement = binding.originalAccessibility;
}

void NGRefreshSwitch(UISwitch *source) {
    if (!NSThread.isMainThread || ![source isKindOfClass:UISwitch.class]) return;
    [NGSeenSwitches() addObject:source];
    if (!NGSwitchEnabled() || !source.superview || !source.window || CGRectIsEmpty(source.bounds)) { NGRemoveSwitch(source); return; }
    NGSwitchBinding *binding = objc_getAssociatedObject(source,&kNGBindingKey);
    if (!binding) {
        if (!NGBundleResources()) return; // Do not hide a working native control if resources are missing.
        binding = [NGSwitchBinding new]; binding.source = source;
        binding.originalAlpha = source.alpha; binding.originalAccessibility = source.isAccessibilityElement;
        Class component = NSClassFromString(@"NGTheseusSwitch"); if (!component) return;
        binding.overlay = [[component alloc] initWithFrame:CGRectMake(0,0,63,28)];
        __weak NGSwitchBinding *weak = binding;
        [(id<NGSwitchComponent>)binding.overlay setOnChanged:^(BOOL value) { [weak commit:value]; }];
        binding.overlay.accessibilityIdentifier = @"NGSwitchOverlay";
        binding.overlay.clipsToBounds = NO;
        objc_setAssociatedObject(source,&kNGBindingKey,binding,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    }
    UIView *parent = NGSwitchOverlayHost(source);
    if (binding.overlay.superview != parent) {
        [binding.overlay removeFromSuperview];
        [parent addSubview:binding.overlay];
    }
    // Keep the overlay in the host's coordinate system.  Do not apply the
    // source transform a second time: convertRect already includes it.
    CGSize size = CGSizeMake(63, 28);
    CGRect anchor = [source convertRect:source.bounds toView:parent];
    binding.overlay.transform = CGAffineTransformIdentity;
    binding.overlay.bounds = (CGRect){CGPointZero, size};
    binding.overlay.center = CGPointMake(CGRectGetMidX(anchor), CGRectGetMidY(anchor));
    [parent bringSubviewToFront:binding.overlay];
    binding.overlay.hidden = source.hidden;
    binding.overlay.userInteractionEnabled = source.userInteractionEnabled;
    binding.overlay.alpha = binding.originalAlpha;
    binding.modifyingNative = YES;
    source.alpha = 0; source.isAccessibilityElement = NO;
    binding.modifyingNative = NO;
    NGSyncSwitch(source, NO);
}

void NGRefreshAllSwitches(void) {
    for (UISwitch *source in NGSeenSwitches().allObjects) NGRefreshSwitch(source);
}

BOOL NGHandleSwitchAlpha(UISwitch *source, CGFloat alpha) {
    NGSwitchBinding *binding = objc_getAssociatedObject(source,&kNGBindingKey);
    if (!binding || binding.modifyingNative) return NO;
    binding.originalAlpha = alpha;
    binding.overlay.alpha = alpha;
    return YES;
}
