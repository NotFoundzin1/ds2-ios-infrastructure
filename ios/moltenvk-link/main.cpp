#include <vulkan/vulkan.h>

int main(int argc, char** argv) {
    const char* symbol = argc > 1 ? argv[1] : "vkCreateInstance";
    return vkGetInstanceProcAddr(VK_NULL_HANDLE, symbol) == nullptr ? 1 : 0;
}
