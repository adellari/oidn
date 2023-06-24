// Copyright 2023 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "context.h"

OIDN_NAMESPACE_BEGIN

  Context& Context::get()
  {
    static Context instance;
    return instance;
  }

  void Context::init()
  {
    std::call_once(initFlag, [this]()
    {
      getEnvVar("OIDN_VERBOSE", verbose);

      // Load the modules
    #if defined(OIDN_DEVICE_CPU)
      if (getEnvVarOrDefault("OIDN_DEVICE_CPU", 1))
        modules.load("device_cpu");
    #endif
    #if defined(OIDN_DEVICE_SYCL)
      if (getEnvVarOrDefault("OIDN_DEVICE_SYCL", 1))
        modules.load("device_sycl");
    #endif
    #if defined(OIDN_DEVICE_CUDA)
      if (getEnvVarOrDefault("OIDN_DEVICE_CUDA", 1))
        modules.load("device_cuda");
    #endif
    #if defined(OIDN_DEVICE_HIP)
      if (getEnvVarOrDefault("OIDN_DEVICE_HIP", 1))
        modules.load("device_hip");
    #endif
    #if defined(OIDN_DEVICE_METAL)
      if (getEnvVarOrDefault("OIDN_DEVICE_METAL", 1))
        modules.load("device_metal");
    #endif

      // Sort the physical devices by score
      std::sort(physicalDevices.begin(), physicalDevices.end(),
                [](const Ref<PhysicalDevice>& a, const Ref<PhysicalDevice>& b)
                { return a->score > b->score; });
    });
  }

  bool Context::isDeviceSupported(DeviceType type) const
  {
    return deviceFactories.find(type) != deviceFactories.end();
  }

  DeviceFactory* Context::getDeviceFactory(DeviceType type) const
  {
    auto it = deviceFactories.find(type);
    if (it == deviceFactories.end())
      throw Exception(Error::UnsupportedHardware, "unsupported device type: " + toString(type));
    return it->second.get();
  }

  const Ref<PhysicalDevice>& Context::getPhysicalDevice(int id) const
  {
    if (id < 0 || static_cast<size_t>(id) >= physicalDevices.size())
      throw Exception(Error::InvalidArgument, "invalid physical device ID: " + toString(id));
    return physicalDevices[id];
  }

  Ref<Device> Context::newDevice(int physicalDeviceID)
  {
    const auto& physicalDevice = getPhysicalDevice(physicalDeviceID);
    const DeviceType type = physicalDevice->type;
    return getDeviceFactory(type)->newDevice(physicalDevice);
  }

OIDN_NAMESPACE_END