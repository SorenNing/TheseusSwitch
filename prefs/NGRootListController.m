#import <UIKit/UIKit.h>
#import "Bridge.h"
#include <notify.h>
#import <objc/runtime.h>

@class PSSpecifier;
@interface PSListController : UIViewController
- (NSArray *)loadSpecifiersFromPlistName:(NSString *)name target:(id)target;
@end
@interface PSSpecifier : NSObject
- (id)propertyForKey:(NSString *)key;
@end

@interface NGRootListController : PSListController
@property(nonatomic,strong) NSArray *ngSpecifiers;
@end

@implementation NGRootListController
- (NSArray *)specifiers {
    if (!self.ngSpecifiers) {
        self.ngSpecifiers = [self loadSpecifiersFromPlistName:@"Root" target:self];
        // Let inherited PSListController table methods see the same array.
        // Runtime metadata avoids assuming PSViewController's private ivar size.
        Ivar ivar = class_getInstanceVariable(PSListController.class,"_specifiers");
        if (ivar && ivar_getTypeEncoding(ivar)[0] == '@') object_setIvar(self,ivar,self.ngSpecifiers);
    }
    return self.ngSpecifiers;
}
- (id)readPreferenceValue:(PSSpecifier *)specifier {
    id value = NGReadPreferences()[[specifier propertyForKey:@"key"]];
    return value ?: [specifier propertyForKey:@"default"];
}
- (void)setPreferenceValue:(id)value specifier:(PSSpecifier *)specifier {
    NSString *key = [specifier propertyForKey:@"key"];
    if (NGStorePreference(key,value)) notify_post("com.ning.theseusswitch/changed");
}
@end
