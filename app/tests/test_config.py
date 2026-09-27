import json
import sys
import copy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import DEFAULT_CONFIG, load_config, normalize_config, save_config


def test_load_config_creates_defaults(tmp_path):
    path = tmp_path / "config.json"
    config = load_config(path)

    assert config["active_provider"] == DEFAULT_CONFIG["active_provider"]
    assert config["default_output_dir"] == ""
    assert config["generation_path_history"] == []
    assert config["default_size"] == "1024x1024"
    assert config["default_resolution"] == "1K"
    assert config["default_aspect_ratio"] == "1:1"
    assert config["default_clarity"] == "1K"
    assert config["custom_generation_sizes"] == []
    assert config["save_layout"] == "double"
    provider = config["providers"]["aiapis_gpt_image_2"]
    assert provider["adapter"] == "openai"
    assert provider["openai_call_method"] == "gpt-image-2"
    assert provider["openai_example_mode"] == "text_to_image"
    assert provider["code_examples"] == {}
    assert provider["custom_scripts"] == {}
    assert provider["quality"] == "high"
    assert provider["output_format"] == "png"
    assert provider["output_compression"] == 80
    assert provider["background"] == "auto"
    assert provider["moderation"] == "low"
    assert provider["stream"] is False
    assert provider["partial_images"] == 0
    assert provider["user"] == ""
    assert provider["user_agent"] == ""
    assert provider["proxy_mode"] == "system"
    assert provider["proxy_url"] == ""
    assert provider["allow_untrusted_proxy_certificate"] is True
    assert "default_size" not in config["providers"]["aiapis_gpt_image_2"]
    assert path.exists()


def test_v059_normalize_config_dedupes_generation_path_history():
    config = normalize_config(
        {
            "generation_path_history": [
                "D:\\AI\\A",
                "",
                "D:\\AI\\B",
                "D:\\AI\\A",
                None,
                "  D:\\AI\\C  ",
            ]
        }
    )

    assert config["generation_path_history"] == [
        "D:\\AI\\A",
        "D:\\AI\\B",
        "D:\\AI\\C",
    ]


def test_v061_normalize_config_dedupes_provider_field_history_without_api_key():
    config = normalize_config(
        {
            "provider_field_history": {
                "api_key_env": ["IMG_API_KEY", "", "CUSTOM_KEY", "IMG_API_KEY"],
                "model": ["gpt-image-2-standard", "gpt-image-2", "gpt-image-2-standard"],
                "user_agent": [" UA-A ", "UA-B", "UA-A"],
                "api_key": ["secret-should-not-be-kept"],
            }
        }
    )

    assert config["provider_field_history"] == {
        "api_key_env": ["IMG_API_KEY", "CUSTOM_KEY"],
        "model": ["gpt-image-2-standard", "gpt-image-2"],
        "user_agent": ["UA-A", "UA-B"],
    }
    assert "api_key" not in config["provider_field_history"]


def test_save_config_round_trips(tmp_path):
    path = tmp_path / "config.json"
    config = load_config(path)
    config["default_output_dir"] = "D:\\AIOutput"
    config["providers"]["aiapis_gpt_image_2"]["model"] = "gpt-image-2"

    save_config(path, config)

    loaded = load_config(path)
    assert loaded["default_output_dir"] == "D:\\AIOutput"
    assert loaded["providers"]["aiapis_gpt_image_2"]["model"] == "gpt-image-2"


def test_load_config_recovers_non_object_root(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("[]", encoding="utf-8")

    config = load_config(path)

    assert config == DEFAULT_CONFIG
    assert json.loads(path.read_text(encoding="utf-8")) == DEFAULT_CONFIG


def test_load_config_recovers_incompatible_provider_section(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps({"default_output_dir": "D:\\AIOutput", "providers": []}),
        encoding="utf-8",
    )

    config = load_config(path)

    assert config["default_output_dir"] == "D:\\AIOutput"
    assert config["providers"] == DEFAULT_CONFIG["providers"]
    assert json.loads(path.read_text(encoding="utf-8")) == config


def test_normalize_config_accepts_only_supported_default_resolution():
    valid = normalize_config({"default_resolution": "4K"})
    custom = normalize_config(
        {
            "default_resolution": "custom",
            "default_custom_resolution": "custom-hires",
            "default_count": 3,
        }
    )
    invalid = normalize_config({"default_resolution": "8K"})

    assert valid["default_resolution"] == "4K"
    assert custom["default_resolution"] == "custom"
    assert custom["default_custom_resolution"] == "custom-hires"
    assert custom["default_count"] == 3
    assert invalid["default_resolution"] == "1K"


def test_normalize_config_accepts_aspect_ratio_clarity_and_custom_sizes():
    config = normalize_config(
        {
            "default_aspect_ratio": "16:9",
            "default_clarity": "custom",
            "default_size": "1234x567",
            "custom_generation_sizes": [
                "1234x567",
                "1234x567",
                "0x512",
                "512x0",
                "abc",
                "",
            ],
        }
    )

    assert config["default_aspect_ratio"] == "16:9"
    assert config["default_clarity"] == "custom"
    assert config["default_size"] == "1234x567"
    assert config["default_resolution"] == "custom"
    assert config["custom_generation_sizes"] == ["1234x567"]


def test_normalize_config_migrates_legacy_size_and_resolution_to_v012_fields():
    preset = normalize_config({"default_size": "2048x1152", "default_resolution": "2K"})
    custom = normalize_config({"default_size": "1234x567", "default_resolution": "custom"})

    assert preset["default_aspect_ratio"] == "16:9"
    assert preset["default_clarity"] == "2K"
    assert preset["default_size"] == "2048x1152"
    assert preset["custom_generation_sizes"] == []
    assert custom["default_aspect_ratio"] == "1:1"
    assert custom["default_clarity"] == "custom"
    assert custom["default_size"] == "1234x567"
    assert custom["custom_generation_sizes"] == ["1234x567"]


def test_normalize_config_does_not_restore_deleted_default_provider():
    config = normalize_config(
        {
            "active_provider": "custom_provider",
            "providers": {
                "custom_provider": {
                    "display_name": "Custom",
                    "adapter": "openai",
                    "base_url": "https://example.test/v1",
                    "api_key": "key",
                    "api_key_env": "",
                    "model": "gpt-image-2",
                }
            },
        }
    )

    assert list(config["providers"]) == ["custom_provider"]
    assert config["active_provider"] == "custom_provider"


def test_normalize_config_allows_empty_provider_collection():
    config = normalize_config({"active_provider": "missing", "providers": {}})

    assert config["providers"] == {}
    assert config["active_provider"] == ""


def test_normalize_config_selects_first_provider_when_active_deleted():
    config = normalize_config(
        {
            "active_provider": "deleted",
            "providers": {
                "first": {"adapter": "openai"},
                "second": {"adapter": "openai"},
            },
        }
    )

    assert config["active_provider"] == "first"


def test_normalize_config_migrates_legacy_provider_adapter_to_openai():
    config = normalize_config(
        {
            "active_provider": "legacy",
            "providers": {
                "legacy": {
                    "display_name": "Legacy",
                    "base_url": "https://legacy.test/v1",
                },
                "aiapis_gpt_image_2": {
                    "display_name": "Built in key",
                },
            },
        }
    )

    assert config["providers"]["legacy"]["adapter"] == "openai"
    assert config["providers"]["aiapis_gpt_image_2"]["adapter"] == "openai"
    assert config["providers"]["legacy"]["openai_call_method"] == "gpt-image-2"


def test_normalize_config_preserves_legacy_provider_fields_when_adapter_migrates():
    config = normalize_config(
        {
            "active_provider": "custom",
            "providers": {
                "custom": {
                    "display_name": "代理商 A",
                    "adapter": "aiapis_gpt_image_2",
                    "base_url": "https://proxy.example/v1",
                    "api_key": "secret",
                    "api_key_env": "CUSTOM_KEY",
                    "user_agent": "Mozilla/5.0 PowerShell/7.4",
                    "model": "old-model",
                }
            },
        }
    )

    provider = config["providers"]["custom"]
    assert provider["adapter"] == "openai"
    assert provider["display_name"] == "代理商 A"
    assert provider["base_url"] == "https://proxy.example/v1"
    assert provider["api_key"] == "secret"
    assert provider["api_key_env"] == "CUSTOM_KEY"
    assert provider["user_agent"] == "Mozilla/5.0 PowerShell/7.4"
    assert provider["model"] == "old-model"
    assert provider["openai_call_method"] == "gpt-image-2"
    assert provider["openai_example_mode"] == "text_to_image"
    assert provider["quality"] == "high"
    assert provider["output_format"] == "png"
    assert provider["background"] == "auto"
    assert provider["moderation"] == "low"


def test_normalize_config_defaults_and_preserves_user_agent():
    config = normalize_config(
        {
            "providers": {
                "empty": {"adapter": "openai"},
                "with_ua": {
                    "adapter": "openai",
                    "user_agent": "  Mozilla/5.0 PowerShell/7.4  ",
                },
            }
        }
    )

    assert config["providers"]["empty"]["user_agent"] == ""
    assert config["providers"]["with_ua"]["user_agent"] == (
        "Mozilla/5.0 PowerShell/7.4"
    )


def test_v057_normalize_config_defaults_and_preserves_provider_proxy_settings():
    config = normalize_config(
        {
            "providers": {
                "legacy": {"adapter": "openai"},
                "custom": {
                    "adapter": "openai",
                    "proxy_mode": "custom",
                    "proxy_url": "  http://127.0.0.1:7890  ",
                    "allow_untrusted_proxy_certificate": False,
                },
                "none": {
                    "adapter": "openai",
                    "proxy_mode": "none",
                    "proxy_url": "http://ignored.local:7890",
                    "allow_untrusted_proxy_certificate": "true",
                },
                "bad": {
                    "adapter": "openai",
                    "proxy_mode": "bad",
                    "proxy_url": "http://bad.local:7890",
                },
            },
        }
    )

    assert config["providers"]["legacy"]["proxy_mode"] == "system"
    assert config["providers"]["legacy"]["proxy_url"] == ""
    assert config["providers"]["legacy"]["allow_untrusted_proxy_certificate"] is True
    assert config["providers"]["custom"]["proxy_mode"] == "custom"
    assert config["providers"]["custom"]["proxy_url"] == "http://127.0.0.1:7890"
    assert config["providers"]["custom"]["allow_untrusted_proxy_certificate"] is False
    assert config["providers"]["none"]["proxy_mode"] == "none"
    assert config["providers"]["none"]["proxy_url"] == "http://ignored.local:7890"
    assert config["providers"]["none"]["allow_untrusted_proxy_certificate"] is True
    assert config["providers"]["bad"]["proxy_mode"] == "system"


def test_normalize_config_normalizes_openai_root_base_url_to_v1():
    config = normalize_config(
        {
            "providers": {
                "imgv2": {
                    "adapter": "openai",
                    "base_url": "https://imgv2.aiapis.help/",
                },
                "already_v1": {
                    "adapter": "openai",
                    "base_url": "https://imgv2.aiapis.help/v1",
                },
            }
        }
    )

    assert config["providers"]["imgv2"]["base_url"] == "https://imgv2.aiapis.help/v1"
    assert config["providers"]["already_v1"]["base_url"] == "https://imgv2.aiapis.help/v1"


def test_normalize_config_accepts_google_and_other_adapters():
    config = normalize_config(
        {
            "active_provider": "google_provider",
            "providers": {
                "google_provider": {"adapter": "google"},
                "other_provider": {"adapter": "other"},
            },
        }
    )

    assert config["providers"]["google_provider"]["adapter"] == "google"
    assert config["providers"]["other_provider"]["adapter"] == "other"


def test_v071_normalize_config_accepts_new_shared_script_adapters():
    config = normalize_config(
        {
            "providers": {
                "sysrv": {
                    "adapter": "sysrv-google",
                    "base_url": "https://sysrv.example",
                    "api_key_env": "SYSRV_KEY",
                    "model": "gemini-image",
                    "google_role": "assistant",
                    "request_timeout_seconds": 240,
                    "download_timeout_seconds": 90,
                    "max_retry_attempts": 3,
                },
                "apimart": {
                    "adapter": "apimart-openai",
                    "base_url": "https://api.apimart.ai",
                    "api_key_env": "APIMART_KEY",
                    "model": "gpt-image-2",
                    "apimart_task_timeout_seconds": 360,
                    "apimart_task_poll_interval_seconds": 7,
                    "input_fidelity": "high",
                    "mask_path": "D:\\mask.png",
                },
            }
        }
    )

    sysrv = config["providers"]["sysrv"]
    assert sysrv["adapter"] == "sysrv-google"
    assert sysrv["base_url"] == "https://sysrv.example"
    assert sysrv["api_key_env"] == "SYSRV_KEY"
    assert sysrv["model"] == "gemini-image"
    assert sysrv["google_role"] == "assistant"
    assert sysrv["request_timeout_seconds"] == 240
    assert sysrv["download_timeout_seconds"] == 90
    assert sysrv["max_retry_attempts"] == 3

    apimart = config["providers"]["apimart"]
    assert apimart["adapter"] == "apimart-openai"
    assert apimart["base_url"] == "https://api.apimart.ai/v1"
    assert apimart["api_key_env"] == "APIMART_KEY"
    assert apimart["model"] == "gpt-image-2"
    assert apimart["apimart_task_timeout_seconds"] == 360
    assert apimart["apimart_task_poll_interval_seconds"] == 7
    assert apimart["input_fidelity"] == "high"
    assert apimart["mask_path"] == "D:\\mask.png"


def test_v058_normalize_config_accepts_openai_google_and_google_api_params():
    config = normalize_config(
        {
            "active_provider": "xiaoyun",
            "providers": {
                "xiaoyun": {
                    "adapter": "openai-google",
                    "base_url": "https://www.xiaoyunapi.com/",
                    "api_key_env": "XIAOYUN_API_KEY",
                    "model": "gemini-3.1-flash-image-preview",
                    "google_role": " assistant ",
                    "google_max_tokens": "8192",
                    "google_temperature": "0.7",
                    "google_top_p": "0.9",
                    "google_stream": "true",
                    "google_stop": "END",
                    "google_presence_penalty": "0.1",
                    "google_frequency_penalty": "0.2",
                    "google_logit_bias": "{\"42\": 1}",
                    "google_user": "operator",
                    "google_response_format": "{\"type\":\"json_object\"}",
                    "google_seen": "scene-a",
                    "google_tools": "[{\"type\":\"function\"}]",
                    "google_tool_choice": "auto",
                    "openai_example_mode": "image_to_image",
                }
            },
        }
    )

    provider = config["providers"]["xiaoyun"]
    assert provider["adapter"] == "openai-google"
    assert provider["base_url"] == "https://www.xiaoyunapi.com"
    assert provider["api_key_env"] == "XIAOYUN_API_KEY"
    assert provider["model"] == "gemini-3.1-flash-image-preview"
    assert provider["google_role"] == "assistant"
    assert provider["google_max_tokens"] == 8192
    assert provider["google_temperature"] == "0.7"
    assert provider["google_top_p"] == "0.9"
    assert provider["google_stream"] is False
    assert provider["google_stop"] == "END"
    assert provider["google_presence_penalty"] == "0.1"
    assert provider["google_frequency_penalty"] == "0.2"
    assert provider["google_logit_bias"] == "{\"42\": 1}"
    assert provider["google_user"] == "operator"
    assert provider["google_response_format"] == "{\"type\":\"json_object\"}"
    assert provider["google_seen"] == "scene-a"
    assert provider["google_tools"] == "[{\"type\":\"function\"}]"
    assert provider["google_tool_choice"] == "auto"
    assert provider["openai_example_mode"] == "image_to_image"


def test_v058_normalize_config_defaults_openai_google_fields():
    config = normalize_config(
        {
            "providers": {
                "xiaoyun": {
                    "adapter": "openai-google",
                }
            },
        }
    )

    provider = config["providers"]["xiaoyun"]
    assert provider["base_url"] == "https://www.xiaoyunapi.com/v1"
    assert provider["api_key_env"] == "XIAOYUN_API_KEY"
    assert provider["model"] == "gemini-3.1-flash-image-preview"
    assert provider["google_role"] == "user"
    assert provider["google_max_tokens"] == 4096
    assert provider["google_stream"] is False
    assert provider["google_temperature"] == ""
    assert provider["google_top_p"] == ""
    assert provider["google_stop"] == ""
    assert provider["google_presence_penalty"] == ""
    assert provider["google_frequency_penalty"] == ""
    assert provider["google_logit_bias"] == ""
    assert provider["google_user"] == ""
    assert provider["google_response_format"] == ""
    assert provider["google_seen"] == ""
    assert provider["google_tools"] == ""
    assert provider["google_tool_choice"] == ""


def test_v060_normalize_config_preserves_explicit_blank_connection_fields():
    config = normalize_config(
        {
            "active_provider": "blank_new_provider",
            "providers": {
                "blank_new_provider": {
                    "display_name": "",
                    "adapter": "openai",
                    "base_url": "",
                    "api_key": "",
                    "api_key_env": "",
                    "model": "",
                    "user_agent": "",
                    "proxy_url": "",
                }
            },
        }
    )

    provider = config["providers"]["blank_new_provider"]
    assert provider["adapter"] == "openai"
    assert provider["display_name"] == ""
    assert provider["base_url"] == ""
    assert provider["api_key"] == ""
    assert provider["api_key_env"] == ""
    assert provider["model"] == ""
    assert provider["user_agent"] == ""
    assert provider["proxy_url"] == ""


def test_v060_normalize_config_still_defaults_missing_legacy_connection_fields():
    config = normalize_config(
        {
            "providers": {
                "legacy_openai": {"adapter": "openai"},
            },
        }
    )

    provider = config["providers"]["legacy_openai"]
    assert provider["base_url"] == "https://img.aiapis.help/v1"
    assert provider["api_key_env"] == "IMG_API_KEY"
    assert provider["model"] == "gpt-image-2"


def test_normalize_config_strips_per_provider_capability_overrides():
    config = normalize_config(
        {
            "providers": {
                "proxy": {
                    "adapter": "openai",
                    "supports_text_to_image": False,
                    "supports_image_to_image": False,
                    "supports_count": False,
                    "capabilities": {"supports_count": False},
                }
            },
        }
    )

    provider = config["providers"]["proxy"]
    assert "supports_text_to_image" not in provider
    assert "supports_image_to_image" not in provider
    assert "supports_count" not in provider
    assert "capabilities" not in provider


def test_normalize_config_accepts_only_supported_openai_call_methods():
    response_config = normalize_config(
        {
            "providers": {
                "response_provider": {
                    "adapter": "openai",
                    "openai_call_method": "response",
                    "background": "transparent",
                }
            },
        }
    )
    invalid_config = normalize_config(
        {
            "providers": {
                "invalid_provider": {
                    "adapter": "openai",
                    "openai_call_method": "bad",
                }
            },
        }
    )

    assert response_config["providers"]["response_provider"]["openai_call_method"] == "response"
    assert response_config["providers"]["response_provider"]["background"] == "transparent"
    assert invalid_config["providers"]["invalid_provider"]["openai_call_method"] == "gpt-image-2"


def test_normalize_config_preserves_code_examples_and_custom_scripts_by_method_and_mode():
    config = normalize_config(
        {
            "providers": {
                "custom": {
                    "adapter": "openai",
                    "openai_example_mode": "image_to_image",
                    "code_examples": {
                        "gpt-image-2": {
                            "text_to_image": "print('text')",
                            "image_to_image": "print('image')",
                            "bad_mode": "ignored",
                        },
                        "bad_method": {"text_to_image": "ignored"},
                    },
                    "custom_scripts": {
                        "gpt-image-2": {
                            "text_to_image": "Path(output_path).write_bytes(b'x')",
                        },
                        "response": {
                            "image_to_image": "Path(output_path).write_bytes(b'y')",
                        },
                    },
                }
            },
        }
    )
    invalid = normalize_config(
        {
            "providers": {
                "invalid": {
                    "adapter": "openai",
                    "openai_example_mode": "bad",
                    "code_examples": [],
                    "custom_scripts": "bad",
                }
            },
        }
    )

    provider = config["providers"]["custom"]
    assert provider["openai_example_mode"] == "image_to_image"
    assert provider["code_examples"] == {
        "gpt-image-2": {
            "text_to_image": "print('text')",
            "image_to_image": "print('image')",
        }
    }
    assert provider["custom_scripts"] == {
        "gpt-image-2": {
            "text_to_image": "Path(output_path).write_bytes(b'x')",
        },
        "response": {
            "image_to_image": "Path(output_path).write_bytes(b'y')",
        },
    }
    assert invalid["providers"]["invalid"]["openai_example_mode"] == "text_to_image"
    assert invalid["providers"]["invalid"]["code_examples"] == {}
    assert invalid["providers"]["invalid"]["custom_scripts"] == {}


def test_normalize_config_does_not_mutate_default_config():
    before = copy.deepcopy(DEFAULT_CONFIG)

    normalize_config({"providers": {}})

    assert DEFAULT_CONFIG == before




