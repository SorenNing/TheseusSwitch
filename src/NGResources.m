#import "Bridge.h"
#import <dlfcn.h>
#import <stdlib.h>
#import <unistd.h>

static char kNGResourceAnchor;
static NSString *const kNGDomain = @"com.ning.theseusswitch";

static NSString *NGInstallPrefix(void) {
    Dl_info info = {0};
    if (!dladdr(&kNGResourceAnchor, &info) || !info.dli_fname) return nil;
    char resolved[PATH_MAX] = {0};
    const char *raw = realpath(info.dli_fname, resolved) ?: info.dli_fname;
    NSString *path = [NSString stringWithUTF8String:raw];
    for (NSString *suffix in @[@"/Library/MobileSubstrate/DynamicLibraries/TheseusSwitch.dylib",
                               @"/usr/lib/TweakInject/TheseusSwitch.dylib",
                               @"/Library/PreferenceBundles/TheseusSwitchPrefs.bundle/TheseusSwitchPrefs"]) {
        if ([path hasSuffix:suffix]) return [path substringToIndex:path.length-suffix.length];
    }
    return nil;
}

NSBundle *NGBundleResources(void) {
#ifdef NG_TESTING
    NSString *test = [NSBundle.mainBundle.bundlePath stringByAppendingPathComponent:@"TheseusSwitchResources.bundle"];
    if ([NSFileManager.defaultManager fileExistsAtPath:test]) return [NSBundle bundleWithPath:test];
#endif
    NSString *prefix = NGInstallPrefix();
    if (!prefix) return nil;
    NSString *path = [prefix stringByAppendingPathComponent:@"Library/Application Support/TheseusSwitch/TheseusSwitchResources.bundle"];
    return [NSBundle bundleWithPath:path];
}


NSArray<NSString *> *NGPreferencePaths(void) {
#ifdef NG_TESTING
    NSString *testPath = NSProcessInfo.processInfo.environment[@"NG_TEST_PREFS"];
    if (!testPath.length) testPath = [NSTemporaryDirectory() stringByAppendingPathComponent:@"theseusswitch-test.plist"];
    return @[testPath];
#endif
    NSString *base = @"/var/mobile/Library/Preferences/com.ning.theseusswitch.plist";
    NSString *prefix = NGInstallPrefix();
    if (!prefix.length || [prefix isEqualToString:@"/var/jb"]) return @[base];
    NSString *redirected = [prefix stringByAppendingPathComponent:[base substringFromIndex:1]];
    return [base isEqualToString:redirected] ? @[base] : @[base,redirected];
}

NSDictionary *NGReadPreferences(void) {
    NSDictionary *current = @{}; NSDate *latest = nil;
    for (NSString *path in NGPreferencePaths()) {
        NSDictionary *data = [NSDictionary dictionaryWithContentsOfFile:path];
        NSDate *date = [NSFileManager.defaultManager attributesOfItemAtPath:path error:NULL][NSFileModificationDate];
        if (data && (!latest || [date compare:latest] != NSOrderedAscending)) { current = data; latest = date; }
    }
    NSMutableDictionary *result = [current mutableCopy];
    for (NSString *key in @[@"enabledSwitch"]) {
        if (result[key]) continue;
        id value = CFBridgingRelease(CFPreferencesCopyAppValue((__bridge CFStringRef)key,(__bridge CFStringRef)kNGDomain));
        if (value) result[key] = value;
    }
    return result;
}

BOOL NGStorePreference(NSString *key, id value) {
    if (![@[@"enabledSwitch"] containsObject:key] || ![value isKindOfClass:NSNumber.class]) return NO;
    NSMutableDictionary *data = [NGReadPreferences() mutableCopy]; data[key] = value;
    CFPreferencesSetAppValue((__bridge CFStringRef)key,(__bridge CFPropertyListRef)value,(__bridge CFStringRef)kNGDomain);
    BOOL saved = CFPreferencesAppSynchronize((__bridge CFStringRef)kNGDomain);
    for (NSString *path in NGPreferencePaths()) saved = [data writeToFile:path atomically:YES] || saved;
    return saved;
}
