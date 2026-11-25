#import <Metal/Metal.h>
#import <UIKit/UIKit.h>
#include <dispatch/dispatch.h>
#include <dlfcn.h>

extern int probe_plugin_value(void);

static BOOL CheckFrameworks(void) {
    NSString *path = [NSBundle.mainBundle.privateFrameworksPath
        stringByAppendingPathComponent:@"ProbePlugin.framework/ProbePlugin"];
    void *image = dlopen(path.fileSystemRepresentation, RTLD_NOW | RTLD_LOCAL);
    if (!image) {
        NSLog(@"Framework load failed: %s", dlerror());
        return NO;
    }
    int (*value)(void) = (int (*)(void))dlsym(image, "probe_plugin_value");
    BOOL passed = value && value() == 42 && probe_plugin_value() == 42;
    dlclose(image);
    return passed;
}

@interface ProbeDelegate : UIResponder <UIApplicationDelegate>
@end

@implementation ProbeDelegate
@end

@interface ProbeSceneDelegate : UIResponder <UIWindowSceneDelegate>
@property(nonatomic, strong) UIWindow *window;
@end

@implementation ProbeSceneDelegate
- (void)scene:(UIScene *)scene
    willConnectToSession:(UISceneSession *)session
                 options:(UISceneConnectionOptions *)options {
    if (![scene isKindOfClass:UIWindowScene.class]) {
        return;
    }
    self.window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
    UIViewController *controller = [[UIViewController alloc] init];
    UILabel *label = [[UILabel alloc] initWithFrame:controller.view.bounds];
    label.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    label.backgroundColor = UIColor.systemBackgroundColor;
    label.textAlignment = NSTextAlignmentCenter;
    label.numberOfLines = 0;
    BOOL frameworks = CheckFrameworks();
    NSString *prefix = frameworks ? @"Frameworks: OK" : @"Frameworks: failed";
    label.text = [prefix stringByAppendingString:@"\nMetal: checking"];
    [controller.view addSubview:label];
    self.window.rootViewController = controller;
    [self.window makeKeyAndVisible];

    id<MTLDevice> device = MTLCreateSystemDefaultDevice();
    id<MTLCommandQueue> queue = [device newCommandQueue];
    id<MTLCommandBuffer> buffer = [queue commandBuffer];
    if (!buffer) {
        label.text = [prefix stringByAppendingString:@"\nMetal: command buffer unavailable"];
        NSLog(@"%@", label.text);
        return;
    }
    [buffer addCompletedHandler:^(id<MTLCommandBuffer> result) {
        BOOL passed = result.status == MTLCommandBufferStatusCompleted;
        if (!passed) {
            NSLog(@"Metal command buffer failed: %@", result.error);
        }
        dispatch_async(dispatch_get_main_queue(), ^{
            label.text = [prefix stringByAppendingString:passed ? @"\nMetal: OK" : @"\nMetal: failed"];
            NSLog(@"%@", label.text);
        });
    }];
    [buffer commit];
}
@end

int main(int argc, char **argv) {
    @autoreleasepool {
        return UIApplicationMain(argc, argv, nil, NSStringFromClass(ProbeDelegate.class));
    }
}
