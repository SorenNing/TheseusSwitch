#pragma once
#import <UIKit/UIKit.h>
@class PSSpecifier;
@interface PSViewController : UIViewController
@end
@interface PSListController : PSViewController {
@protected
    NSArray *_specifiers;
}
- (NSArray *)loadSpecifiersFromPlistName:(NSString *)name target:(id)target;
- (NSArray *)specifiers;
- (void)reloadSpecifiers;
- (id)readPreferenceValue:(PSSpecifier *)specifier;
- (void)setPreferenceValue:(id)value specifier:(PSSpecifier *)specifier;
@end
