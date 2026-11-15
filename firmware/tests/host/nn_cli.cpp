// Host harness for the integer NN engine.
//   nn_cli <in.bin> <out.bin>
// in.bin : N windows, each IN_CH x LEN int16 (channels first)
// out.bin: N windows, each OUT_CH x LEN int16
// Build with -DSG_MODEL_HEADER="\"/path/to/model.h\"".
#include <stdio.h>

#include "sg_nn.h"
#include SG_MODEL_HEADER

#define IN_CH 2
#define LEN 512

static int16_t arena[SG_MODEL_ARENA];
static int32_t acc[SG_NN_MAX_LEN];

int main(int argc, char** argv) {
  if (argc != 3) return 2;
  FILE* in = fopen(argv[1], "rb");
  FILE* out = fopen(argv[2], "wb");
  if (!in || !out) return 3;
  int n = 0;
  while (fread(arena + SG_MODEL_IN_OFFSET, sizeof(int16_t), IN_CH * LEN, in) == (size_t)(IN_CH * LEN)) {
    sg_nn_run(SG_MODEL_OPS, SG_MODEL_N_OPS, arena, acc);
    fwrite(arena + SG_MODEL_OUT_OFFSET, sizeof(int16_t), SG_MODEL_OUT_CHANNELS * LEN, out);
    n++;
  }
  fclose(in);
  fclose(out);
  printf("%d windows, arena %d int16, %d params, %d MACs\n", n, SG_MODEL_ARENA, SG_MODEL_PARAMS, SG_MODEL_MACS);
  return 0;
}
