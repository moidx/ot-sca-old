import binascii
from Crypto.Cipher import AES
import numpy as np
import time
from tqdm import tqdm
import yaml

import chipwhisperer as cw

from util import device
from util import plot


def initialize_test(device_cfg):
  """Initialize test setup."""
  ot = device.OpenTitan(
    device_cfg['fpga_bitstream'],
    device_cfg['fw_bin'],
    device_cfg['pll_frequency'],
    device_cfg['baudrate'])
  ot.initialize()
  return ot


# Based on https://github.com/newaetech/chipwhisperer-jupyter/blob/master/PA_HW_CW305_1-Attacking_AES_on_an_FPGA.ipynb
def run_capture(capture_cfg, ot):
  """Run capture."""

  # Key and plaintext generator
  ktp = cw.ktp.Basic()
  ktp.key_len = capture_cfg['key_len_bytes']
  ktp.text_len = capture_cfg['plain_text_len_bytes']
  ot.target.output_len = capture_cfg['plain_text_len_bytes']

  key, text = ktp.next()

  cipher = AES.new(bytes(key), AES.MODE_ECB)
  print('Using key: {}'.format(binascii.b2a_hex(bytes(key))))

  traces = []
  textin = []
  keys = []

  print('Reading from FPGA using simpleserial protocol.')
  ot.target.write('v'+'\n')
  time.sleep(0.5)
  print('Checking version: {}'.format(ot.target.read().strip()))

  project_file = capture_cfg['project_file']
  project = cw.create_project(project_file, overwrite=True)

  for i in tqdm(range(capture_cfg['num_traces']), desc='Capturing', ncols=80):
    key, text = ktp.next()
    textin.append(text)
    keys.append(key)

    ret = cw.capture_trace(ot.scope, ot.target, text, key)
    if not ret:
        print('Failed capture')
        continue
    expected = binascii.b2a_hex(cipher.encrypt(bytes(text)))
    got = binascii.b2a_hex(ret.textout)
    assert (got == expected), (
        'Incorrect encryption result!\nGot {}\nExp {}\n'.format(
         got, expected))

    traces.append(ret.wave)
    project.traces.append(ret)

    ot.target.flush()

  project.save()
  ot.scope.dis()
  ot.target.dis()
  print('Saving sample trace image to: {}'.format(
      capture_cfg['trace_image_filename']))
  plot.save_plot_to_file(traces, capture_cfg['trace_image_filename'])


if __name__ == "__main__":
  with open('capture.yaml') as f:
    cfg_file = yaml.load(f, Loader=yaml.FullLoader)
  ot = initialize_test(cfg_file['device'])
  run_capture(cfg_file['capture'], ot)
