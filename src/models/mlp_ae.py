from .mlp import LazyMLP
import typing as th
import torch


class MLPAutoEncoder(torch.nn.Sequential):
    def __init__(
        self,
        input_shape: th.Union[th.List[int], th.Tuple[int, int, int]],
        encoder_depth: int,
        decoder_depth: int,
        encoder_width: int,
        decoder_width: int,
        latent_dim: int,
        scaling_factor: float = 0.5,
        encoder_args: th.Optional[dict] = None,  # overrides args for encoder
        decoder_args: th.Optional[dict] = None,  # overrides args for decoder
        vae: bool = False,
        **args: th.Optional[dict],  # see LazyMLP for args
    ):
        super().__init__()

        self.encoder_depth, self.decoder_depth = encoder_depth, decoder_depth
        self.encoder_width, self.decoder_width = encoder_width, decoder_width

        self.input_shape = input_shape if isinstance(input_shape, tuple) else tuple(input_shape)
        self.scaling_factor, self.latent_dim = scaling_factor, latent_dim

        self.vae = vae  # if true, do reparameterization trick

        # check that the scaling factor is valid
        if not (0 < scaling_factor < 1):
            raise ValueError(f"Invalid scaling factor: {scaling_factor}, must be between 0 and 1")

        # check if the number of layers, width and scaling factor are compatabile
        if encoder_width * scaling_factor ** (decoder_depth) % 1 != 0:
            raise ValueError(
                f"Invalid combination of encoder params, encoder_width * scaling_factor ** \
                (encoder_width) must be a positive integer: {encoder_width * scaling_factor ** (encoder_width)}"
            )
        if decoder_width * (1 / scaling_factor) ** (decoder_depth) % 1 != 0:
            raise ValueError(
                f"Invalid combination of encoder params, encoder_width * scaling_factor ** \
                (encoder_width) must be a positive integer: {decoder_width * scaling_factor ** (encoder_width)}"
            )

        args = {} if args is None else args
        encoder_args = args if encoder_args is None else {**args, **encoder_args}
        decoder_args = args if decoder_args is None else {**args, **decoder_args}

        self.encoder = LazyMLP(
            out_features=latent_dim,
            layers=[int(encoder_width * scaling_factor**i) for i in range(encoder_depth)],
            **encoder_args,
        )

        self.decoder = LazyMLP(
            out_features=input_shape[0] * input_shape[1] * input_shape[2],
            layers=[int(decoder_width * scaling_factor**i) for i in range(decoder_depth)][::-1],
            **decoder_args,
        )

    def forward(
        self,
        inputs: th.Optional[torch.Tensor] = None,
        latent: th.Optional[torch.Tensor] = None,
        reparameterize: th.Optional[bool] = None,
    ):
        assert inputs is not None or latent is not None, "Must provide either inputs or latent"
        x = self.encoder(inputs) if latent is None else latent

        reparameterize = reparameterize if reparameterize is not None else self.vae
        if reparameterize:
            # split the latent vector into mean and log variance
            mu, log_variance = x.chunk(2, dim=1)
            # sample from the latent space
            x = mu + torch.exp(log_variance / 2) * torch.randn_like(mu)
        
        x = self.decoder(x)
        return x.view(-1, *self.input_shape)
