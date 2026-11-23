#import "Bridge.h"
#import <objc/runtime.h>
#import <objc/message.h>

static char kNGBindingKey;

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
    // Keep Theseus at its original 63x28 size. The native UISwitch is only
    // the anchor/state source; embedding into UISwitch makes UIKit clip and
    // resize the Metal view. Walk to an ancestor that can contain the fixed
    // overlay, then convert the native switch center into that host's space.
    CGSize size = CGSizeMake(63.0, 28.0);
    UIView *parent = source.superview;
    CGRect anchor = parent ? [source convertRect:source.bounds toView:parent] : CGRectZero;
    while (parent && parent.superview &&
           (parent.clipsToBounds || !CGRectContainsRect(parent.bounds,
               CGRectInset(anchor, -size.width * 0.5, -size.height * 0.5)))) {
        UIView *next = parent.superview;
        anchor = [source convertRect:source.bounds toView:next];
        parent = next;
    }
    if (!parent) return;
    if (binding.overlay.superview != parent) {
        [binding.overlay removeFromSuperview];
        [parent addSubview:binding.overlay];
    }
    binding.overlay.transform = CGAffineTransformIdentity;
    binding.overlay.bounds = (CGRect){CGPointZero, size};
    binding.overlay.center = CGPointMake(CGRectGetMidX(anchor), CGRectGetMidY(anchor));
    [parent bringSubviewToFront:binding.overlay];
    binding.overlay.hidden = source.hidden;
    binding.overlay.userInteractionEnabled = source.userInteractionEnabled;
    binding.overlay.alpha = binding.originalAlpha;
    binding.modifyingNative = YES;
    source.isAccessibilityElement = NO;
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
