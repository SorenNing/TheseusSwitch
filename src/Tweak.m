#import "Bridge.h"
#import <objc/runtime.h>
#import <objc/message.h>
#import <dlfcn.h>

typedef void (*NGHookFunction)(Class, SEL, IMP, IMP *);
static NGHookFunction gNGHook;
static void (*gSWLayout)(id,SEL), (*gSWWindow)(id,SEL), (*gSWParent)(id,SEL);
static void (*gSWOn)(id,SEL,BOOL), (*gSWEnabled)(id,SEL,BOOL), (*gSWHidden)(id,SEL,BOOL);
static void (*gSWAlpha)(id,SEL,CGFloat), (*gSWInteraction)(id,SEL,BOOL);
static void (*gSWOnAnimated)(id,SEL,BOOL,BOOL);

static void NGSwitchLayout(UISwitch *s,SEL c) { if (gSWLayout) gSWLayout(s,c); NGRefreshSwitch(s); }
static void NGSwitchWindow(UISwitch *s,SEL c) { if (gSWWindow) gSWWindow(s,c); NGRefreshSwitch(s); }
static void NGSwitchParent(UISwitch *s,SEL c) { if (gSWParent) gSWParent(s,c); NGRefreshSwitch(s); }
static void NGSwitchOn(UISwitch *s,SEL c,BOOL v) { if (gSWOn) gSWOn(s,c,v); NGSyncSwitch(s,NO); }
static void NGSwitchOnAnimated(UISwitch *s,SEL c,BOOL v,BOOL a) { if (gSWOnAnimated) gSWOnAnimated(s,c,v,a); NGSyncSwitch(s,a); }
static void NGHookSwitchEnabled(UISwitch *s,SEL c,BOOL v) { if (gSWEnabled) gSWEnabled(s,c,v); NGSyncSwitch(s,NO); }
static void NGSwitchHidden(UISwitch *s,SEL c,BOOL v) { if (gSWHidden) gSWHidden(s,c,v); NGRefreshSwitch(s); }
static void NGSwitchAlpha(UISwitch *s,SEL c,CGFloat v) { BOOL replaced=NGHandleSwitchAlpha(s,v); if (gSWAlpha) gSWAlpha(s,c,replaced?0:v); }
static void NGSwitchInteraction(UISwitch *s,SEL c,BOOL v) { if (gSWInteraction) gSWInteraction(s,c,v); NGRefreshSwitch(s); }

static void NGInstallMethod(Class cls, SEL sel, IMP replacement, IMP *original) {
    if (!cls || !gNGHook || !replacement || !original || *original) return;
    Method method = class_getInstanceMethod(cls,sel); if (!method) return;
    // Materialize inherited methods on this class instead of mutating UIView.
    class_addMethod(cls,sel,method_getImplementation(method),method_getTypeEncoding(method));
    gNGHook(cls,sel,replacement,original);
}

static void NGChanged(CFNotificationCenterRef center, void *observer, CFStringRef name, const void *object, CFDictionaryRef info) {
    dispatch_async(dispatch_get_main_queue(), ^{ NGPreferencesReload(); NGRefreshAll(); });
}

#ifndef NG_TESTING
__attribute__((constructor)) static void NGInitialize(void) {
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        NGPreferencesReload();
        CFNotificationCenterAddObserver(CFNotificationCenterGetDarwinNotifyCenter(),NULL,NGChanged,
            CFSTR("com.ning.theseusswitch/changed"),NULL,CFNotificationSuspensionBehaviorDeliverImmediately);
        gNGHook = (NGHookFunction)dlsym(RTLD_DEFAULT,"MSHookMessageEx");
        if (!gNGHook) {
            for (NSString *path in @[@"/usr/lib/libsubstrate.dylib",@"/var/jb/usr/lib/libsubstrate.dylib"]) {
                void *handle=dlopen(path.UTF8String,RTLD_NOW|RTLD_LOCAL);
                if (handle) gNGHook=(NGHookFunction)dlsym(handle,"MSHookMessageEx");
                if (gNGHook) break;
            }
        }
        Class sw = UISwitch.class;
        NGInstallMethod(sw,@selector(layoutSubviews),(IMP)NGSwitchLayout,(IMP *)&gSWLayout);
        NGInstallMethod(sw,@selector(didMoveToWindow),(IMP)NGSwitchWindow,(IMP *)&gSWWindow);
        NGInstallMethod(sw,@selector(didMoveToSuperview),(IMP)NGSwitchParent,(IMP *)&gSWParent);
        NGInstallMethod(sw,@selector(setOn:),(IMP)NGSwitchOn,(IMP *)&gSWOn);
        NGInstallMethod(sw,@selector(setOn:animated:),(IMP)NGSwitchOnAnimated,(IMP *)&gSWOnAnimated);
        NGInstallMethod(sw,@selector(setEnabled:),(IMP)NGHookSwitchEnabled,(IMP *)&gSWEnabled);
        NGInstallMethod(sw,@selector(setHidden:),(IMP)NGSwitchHidden,(IMP *)&gSWHidden);
        NGInstallMethod(sw,@selector(setAlpha:),(IMP)NGSwitchAlpha,(IMP *)&gSWAlpha);
        NGInstallMethod(sw,@selector(setUserInteractionEnabled:),(IMP)NGSwitchInteraction,(IMP *)&gSWInteraction);
    });
}
#endif
