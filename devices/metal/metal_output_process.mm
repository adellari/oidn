// Copyright 2023 Apple Inc.
// SPDX-License-Identifier: Apache-2.0

#include "metal_output_process.h"
#include "metal_engine.h"
#include "metal_common.h"
#include "metal_kernel_common.h"

OIDN_NAMESPACE_BEGIN

  MetalOutputProcess::MetalOutputProcess(const Ref<MetalEngine>& engine, const OutputProcessDesc& desc)
    : OutputProcess(desc),
      engine(engine),
      pipeline(nullptr), commandQueue(nullptr), paramsBuffer(nullptr) {}

  MetalOutputProcess::~MetalOutputProcess()
  {
    cleanup();
  }

  void MetalOutputProcess::cleanup()
  {
    if (pipeline)
      [pipeline release];
    if (commandQueue)
      [commandQueue release];
    if (paramsBuffer)
      [paramsBuffer release];
    
    pipeline = nullptr;
    commandQueue = nullptr;
    paramsBuffer = nullptr;
  }

  void MetalOutputProcess::finalize()
  {
    MTLDevice_t device = static_cast<MetalDevice*>(engine->getDevice())->getMetalDevice();

    pipeline = createPipeline(device, "output_process");
    
    commandQueue = [device newCommandQueue];
    
    if (!commandQueue)
      throw std::runtime_error("can not create command queue");
    
    paramsBuffer = [device newBufferWithLength: sizeof(ProcessParams)
                                       options: MTLResourceStorageModeShared];
  }

  void MetalOutputProcess::submit()
  {
    ProcessParams params = createProcessParams();
    
    void* paramsPtr = [paramsBuffer contents];
    memcpy(paramsPtr, &params, sizeof(params));
    
    MTLBuffer_t bufferInput = getMetalBuffer(src->getBuffer());
    MTLBuffer_t bufferOutput = getMetalBuffer(dst->getBuffer());
    
    auto commandBuffer = [commandQueue commandBuffer];
    auto computeEncoder = [commandBuffer computeCommandEncoder];

    [computeEncoder setComputePipelineState: pipeline];
    
    int index = 0;
    
    [computeEncoder setBuffer: bufferInput
                       offset: 0
                      atIndex: index++];
    
    [computeEncoder setBuffer: bufferOutput
                       offset: 0
                      atIndex: index++];
    
    [computeEncoder setBuffer: paramsBuffer
                       offset: 0
                      atIndex: index++];
    
    auto width = pipeline.threadExecutionWidth;
    auto height = pipeline.maxTotalThreadsPerThreadgroup / width;
    auto threadsPerThreadgroup = MTLSizeMake(width, height, 1);
    auto threadgroupsPerGrid = MTLSizeMake((params.tile.W + width - 1) / width,
                                           (params.tile.H + height - 1) / height, 1);
    
    [computeEncoder dispatchThreadgroups: threadgroupsPerGrid
                   threadsPerThreadgroup: threadsPerThreadgroup];
    
    [computeEncoder endEncoding];
    [commandBuffer commit];
    [commandBuffer waitUntilCompleted];

    [computeEncoder release];
    [commandBuffer release];
  }

  ProcessParams MetalOutputProcess::createProcessParams()
  {
    ProcessParams params = {0};
    params.C = dst->getC();
    params.H = dst->getH();
    params.W = dst->getW();
    params.tile.H = tile.H;
    params.tile.W = tile.W;
    params.tile.hSrcBegin = tile.hSrcBegin;
    params.tile.wSrcBegin = tile.wSrcBegin;
    params.tile.hDstBegin = tile.hDstBegin;
    params.tile.wDstBegin = tile.wDstBegin;
    params.hdr = hdr;
    params.snorm = snorm;
    params.normScale = transferFunc->getNormScale();
    params.func = toTransferFunctionType(transferFunc->getType());
    params.inputScale = transferFunc->getInputScale();
    params.outputScale = transferFunc->getOutputScale();
    params.inputDataType = toDataType(src->getDataType());
    params.outputDataType = toDataType(dst->getDataType());
    return params;
  }

OIDN_NAMESPACE_END