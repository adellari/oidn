// Copyright 2009-2021 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#pragma once

#include "node.h"
#include "upsample_ispc.h"

namespace oidn {

#if defined(OIDN_DNNL)

  // 2x2 nearest-neighbor upsampling node (blocked layout)
  class UpsampleNode : public Node
  {
  private:
    ispc::Upsample impl;

    int K;
    Ref<Tensor> src;
    Ref<Tensor> dst;

  public:
    UpsampleNode(const Ref<Device>& device,
                 int K,
                 const Ref<Tensor>& src,
                 const Ref<Tensor>& dst)
      : Node(device),
        K(K),
        src(src),
        dst(dst)
    {
      impl.src = *src;
      impl.dst = *dst;
    }

    void execute() override
    {
      parallel_nd(impl.src.C / K, impl.src.H, [&](int ck, int h)
      {
        ispc::Upsample_kernel(&impl, ck, h);
      });
    }

    Ref<Tensor> getDst() const override { return dst; }
  };

#else

  // 2x2 nearest-neighbor upsampling node
  class UpsampleNode : public Node
  {
  private:
    Ref<Tensor> src;
    Ref<Tensor> dst;

  public:
    UpsampleNode(const Ref<Device>& device,
                 int K,
                 const Ref<Tensor>& src,
                 const Ref<Tensor>& dst)
      : Node(device),
        src(src),
        dst(dst)
    {
      assert(K == 1);
    }

    void execute() override
    {
      const size_t C = src->dims[0];
      const size_t H = src->dims[1];
      const size_t W = src->dims[2];

      parallel_nd(C, H, [&](int c, int h)
      {
        const size_t offset = (c*H + h) * W;
        const float* srcPtr_line = (float*)src->data() + offset;
        float* dstPtr_line0 = (float*)dst->data() + offset * 4;
        float* dstPtr_line1 = dstPtr_line0 + W*2; // next line

        #pragma unroll(16)
        for (size_t w = 0; w < W; ++w)
        {
          // Load value
          const float value = srcPtr_line[w];

          // Store value 2x2
          dstPtr_line0[w*2  ] = value;
          dstPtr_line0[w*2+1] = value;
          dstPtr_line1[w*2  ] = value;
          dstPtr_line1[w*2+1] = value;
        }
      });
    }

    Ref<Tensor> getDst() const override { return dst; }
  };

#endif

} // namespace oidn
