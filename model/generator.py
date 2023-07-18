import math

import torch
from torch import nn
from torch.nn import functional as F
import torchaudio

class Postnet(torch.nn.Module):

    def __init__(
        self, idim: int,
        odim: int,
        n_layers: int = 5,
        n_chans: int = 512,
        n_filts: int = 5,
        dropout_rate: float = 0.5,
        use_batch_norm: bool = True,
    ):
        super(Postnet, self).__init__()
        self.postnet = torch.nn.ModuleList()
        for layer in range(n_layers - 1):
            ichans = odim if layer == 0 else n_chans
            ochans = odim if layer == n_layers - 1 else n_chans
            if use_batch_norm:
                self.postnet += [
                    torch.nn.Sequential(
                        torch.nn.Conv1d(
                            ichans,
                            ochans,
                            n_filts,
                            stride=1,
                            padding=(n_filts - 1) // 2,
                            bias=False,
                        ),
                        torch.nn.BatchNorm1d(ochans),
                        torch.nn.Tanh(),
                        torch.nn.Dropout(dropout_rate),
                    )
                ]
            else:
                self.postnet += [
                    torch.nn.Sequential(
                        torch.nn.Conv1d(
                            ichans,
                            ochans,
                            n_filts,
                            stride=1,
                            padding=(n_filts - 1) // 2,
                            bias=False,
                        ),
                        torch.nn.Tanh(),
                        torch.nn.Dropout(dropout_rate),
                    )
                ]
        ichans = n_chans if n_layers != 1 else odim
        if use_batch_norm:
            self.postnet += [
                torch.nn.Sequential(
                    torch.nn.Conv1d(
                        ichans,
                        odim,
                        n_filts,
                        stride=1,
                        padding=(n_filts - 1) // 2,
                        bias=False,
                    ),
                    torch.nn.BatchNorm1d(odim),
                    torch.nn.Dropout(dropout_rate),
                )
            ]
        else:
            self.postnet += [
                torch.nn.Sequential(
                    torch.nn.Conv1d(
                        ichans,
                        odim,
                        n_filts,
                        stride=1,
                        padding=(n_filts - 1) // 2,
                        bias=False,
                    ),
                    torch.nn.Dropout(dropout_rate),
                )
            ]

    def forward(self, xs):
        """Calculate forward propagation.
        Args:
            xs (Tensor): Batch of the sequences of padded input tensors (B, idim, Tmax).
        Returns:
            Tensor: Batch of padded output tensor. (B, odim, Tmax).
        """
        for postnet in self.postnet:
            xs = postnet(xs)
        return xs

class ResidualConv1dGLU(nn.Module):
    """Residual dilated conv1d + Gated linear unit
    Args:
        residual_channels (int): Residual input / output channels
        gate_channels (int): Gated activation channels.
        kernel_size (int): Kernel size of convolution layers.
        skip_out_channels (int): Skip connection channels. If None, set to same
          as ``residual_channels``.
        cin_channels (int): Local conditioning channels. If negative value is
          set, local conditioning is disabled.
        gin_channels (int): Global conditioning channels. If negative value is
          set, global conditioning is disabled.
        dropout (float): Dropout probability.
        padding (int): Padding for convolution layers. If None, proper padding
          is computed depends on dilation and kernel_size.
        dilation (int): Dilation factor.
    """

    def __init__(self, residual_channels, gate_channels, kernel_size,
                 skip_out_channels=None,
                 cin_channels=-1, gin_channels=-1,
                 dropout=1 - 0.95, padding=None, dilation=1,
                 bias=True, *args, **kwargs):
        super(ResidualConv1dGLU, self).__init__()
        self.dropout = dropout
        if skip_out_channels is None:
            skip_out_channels = residual_channels
        if padding is None:
            padding = (kernel_size - 1) // 2 * dilation   # For non causal dilated convolution

        self.conv = nn.Conv1d(residual_channels, gate_channels, kernel_size,
                              padding=padding, dilation=dilation,
                              bias=bias, *args, **kwargs)

        # conv output is split into two groups
        gate_out_channels = gate_channels // 2
        self.conv1x1_out = nn.Conv1d(gate_out_channels, residual_channels, 1, bias=bias)
        self.conv1x1_skip = nn.Conv1d(gate_out_channels, skip_out_channels, 1, bias=bias)

    def forward(self, x):
        residual = x
        x = F.dropout(x, p=self.dropout, training=self.training)
        splitdim = 1
        x = self.conv(x)

        a, b = x.split(x.size(splitdim) // 2, dim=splitdim)


        x = torch.tanh(a) * torch.sigmoid(b)

        # For skip connection
        s = self.conv1x1_skip(x)

        # For residual connection
        x = self.conv1x1_out(x)

        x = (x + residual) * math.sqrt(0.5)
        return x, s


class WaveNet(nn.Module):
    def __init__(self, in_channels, out_channels=1, bias=False,
                 num_layers=20, num_stacks=2, kernel_size=3,
                 residual_channels=128, gate_channels=128, skip_out_channels=128,
                 postnet_layers=12, postnet_filts=32, use_batch_norm=False, postnet_dropout_rate=0.5):
        super().__init__()
        assert num_layers % num_stacks == 0
        self.receptive_field = 0
        num_layers_per_stack = num_layers // num_stacks
        self.first_conv = nn.Conv1d(in_channels, residual_channels, 3, padding=1, bias=bias)
        self.conv_layers = nn.ModuleList()
        for n_layer in range(num_layers):
            dilation = 2**(n_layer % num_layers_per_stack)
            self.receptive_field += (kernel_size-1)*dilation
            conv = ResidualConv1dGLU(
                residual_channels, gate_channels,
                skip_out_channels=skip_out_channels,
                kernel_size=kernel_size,
                bias=bias,
                dilation=dilation,
                dropout=1 - 0.95,
            )
            self.conv_layers.append(conv)

        self.last_conv_layers = nn.Sequential(
            nn.ReLU(True),
            nn.Conv1d(skip_out_channels, skip_out_channels, 1, bias=True),
            nn.ReLU(True),
            nn.Conv1d(skip_out_channels, out_channels, 1, bias=True),
        )

        self.postnet = (
            None
            if postnet_layers == 0
            else Postnet(
                idim=in_channels,
                odim=out_channels,
                n_layers=postnet_layers,
                n_chans=residual_channels,
                n_filts=postnet_filts,
                use_batch_norm=use_batch_norm,
                dropout_rate=postnet_dropout_rate,
            )
        )

    def forward(self, x, with_postnet=False):
        x = self.first_conv(x)
        skips = 0
        for conv in self.conv_layers:
            x, h = conv(x)
            skips += h

        skips *= math.sqrt(1.0 / len(self.conv_layers))
        x = skips
        x = self.last_conv_layers(x)
        if not with_postnet:
            return x, None
        else:
            after_x = self.postnet(x)
            return x, after_x



def generator_loss(disc_outputs):
    loss = 0
    gen_losses = []
    for dg in disc_outputs:
        l = torch.mean((1-dg)**2)
        gen_losses.append(l)
        loss += l

    return loss, gen_losses

class BNEGenerator(nn.Module):
    def __init__(self, in_channels, in_sample, out_sample):
        super(BNEGenerator, self).__init__()
        self.wavenet = WaveNet(in_channels)
        self.in_sample = in_sample
        self.out_sample = out_sample
    def forward(self, input):
        input = torchaudio.functional.resample(
            input,
            self.in_sample,
            self.out_sample,
            resampling_method="kaiser_window",
            lowpass_filter_width=16,
            rolloff=0.945,
            beta=14.769656459379492,
        )
        pad = self.wavenet.receptive_field // 2
        input = torch.nn.functional.pad(input, [pad, pad])
        input = self.wavenet(input)[0]
        input = torch.tanh(input)
        input = input[..., pad:-pad]
        return input


if __name__ == '__main__':

    model = BNEGenerator(1, 16000, 48000)
    x = torch.ones([2, 1, 16000])
    y = model(x)
    print("Shape of y", y.shape)