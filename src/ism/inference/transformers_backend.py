"""Real-model ``TextGenerator`` backed by Hugging Face Transformers.

This is the GPU adapter that implements the same contract as
:class:`ism.inference.mock.MockTextGenerator`. Per the architecture rules, the
heavy dependencies (``torch``/``transformers``/``bitsandbytes``) are imported
lazily inside :meth:`_ensure_loaded` so that importing this module — and running
the full local test suite — never requires them. Only an actual generation call
touches the model.
"""

from __future__ import annotations

import importlib
import time
from typing import Any

from ism.inference.contracts import GenerationRequest, GenerationResult
from ism.inference.errors import classify_exception


class TransformersTextGenerator:
    def __init__(
        self,
        *,
        model_name: str,
        model_revision: str,
        tokenizer_revision: str,
        load_in_4bit: bool,
        device: str,
        temperature: float = 0.0,
        apply_chat_template: bool = True,
    ) -> None:
        self.model_name = model_name
        self.model_revision = model_revision
        self.tokenizer_revision = tokenizer_revision
        self.load_in_4bit = load_in_4bit
        self.device = device
        self.temperature = temperature
        self.apply_chat_template = apply_chat_template
        self._torch: Any = None
        self._tokenizer: Any = None
        self._model: Any = None

    @property
    def loaded(self) -> bool:
        """True once the model and tokenizer have been lazily loaded."""
        return self._model is not None

    def generate(
        self,
        requests: tuple[GenerationRequest, ...],
    ) -> tuple[GenerationResult, ...]:
        results: list[GenerationResult] = []
        for request in requests:
            start = time.perf_counter()
            try:
                text, input_tokens, output_tokens = self._generate_text(
                    request.prompt,
                    max_new_tokens=request.max_new_tokens,
                    seed=request.seed,
                )
            except Exception as error:
                results.append(
                    GenerationResult(
                        request_id=request.request_id,
                        error_kind=classify_exception(error),
                        error_message=str(error) or error.__class__.__name__,
                        latency_ms=(time.perf_counter() - start) * 1000,
                    )
                )
                continue
            results.append(
                GenerationResult(
                    request_id=request.request_id,
                    text=text,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=(time.perf_counter() - start) * 1000,
                )
            )
        return tuple(results)

    def _generate_text(
        self,
        prompt: str,
        *,
        max_new_tokens: int,
        seed: int,
    ) -> tuple[str, int, int]:
        """Run one deterministic generation. Returns (text, input_tokens, output_tokens)."""
        self._ensure_loaded()
        torch = self._torch
        tokenizer = self._tokenizer
        model = self._model

        torch.manual_seed(seed)
        if self.device != "cpu":
            torch.cuda.manual_seed_all(seed)

        if self.apply_chat_template and getattr(tokenizer, "chat_template", None):
            input_ids = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                add_generation_prompt=True,
                return_tensors="pt",
            )
        else:
            input_ids = tokenizer(prompt, return_tensors="pt").input_ids
        input_ids = input_ids.to(model.device)
        input_tokens = int(input_ids.shape[1])

        do_sample = self.temperature > 0
        generate_kwargs: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
        }
        if do_sample:
            generate_kwargs["temperature"] = self.temperature

        with torch.inference_mode():
            output = model.generate(input_ids, **generate_kwargs)

        new_tokens = output[0][input_tokens:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True)
        return text, input_tokens, int(new_tokens.shape[0])

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        torch: Any = importlib.import_module("torch")
        transformers: Any = importlib.import_module("transformers")
        self._torch = torch

        quantization_config = None
        if self.load_in_4bit:
            quantization_config = transformers.BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )

        on_gpu = self.device != "cpu"
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            self.model_name,
            revision=self.tokenizer_revision,
        )
        model = transformers.AutoModelForCausalLM.from_pretrained(
            self.model_name,
            revision=self.model_revision,
            quantization_config=quantization_config,
            device_map="auto" if on_gpu else None,
            torch_dtype=torch.float16 if on_gpu else torch.float32,
        )
        if not on_gpu:
            model = model.to("cpu")
        model.eval()
        self._tokenizer = tokenizer
        self._model = model


__all__ = ["TransformersTextGenerator"]
