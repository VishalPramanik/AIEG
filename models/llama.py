# -*- coding: utf-8 -*-
"""Llama.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1q0tGyumekVEVhAT-XXDDe-s7tQ0iTrwF
"""

import torch
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from IPython.display import HTML, display
import re

def AIEG(generated_text, word_index):
    # Step 1: Load the Llama2 7B model and tokenizer
    model_name = "meta-llama/Llama-2-7b-hf"
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name, output_attentions=True)
    model.eval()

    def integrated_gradients(inputs, model, tokenizer, t_idx, baseline=None, steps=50):
        input_ids = tokenizer.encode(inputs, return_tensors="pt")
        embedding_layer = model.get_input_embeddings()

        if baseline is None:
            baseline = torch.zeros_like(embedding_layer(input_ids))

        total_gradients = torch.zeros_like(embedding_layer(input_ids))
        prev = None

        for alpha in torch.linspace(0, 1, steps):
            interpolated_input = baseline + alpha * (embedding_layer(input_ids) - baseline)
            interpolated_input.requires_grad_(True)

            outputs = model(inputs_embeds=interpolated_input)[0]
            output_score = outputs[0, t_idx].sum()

            if prev is not None:
                EF = (output_score - prev) / (output_score + prev + 1e-5)
            else:
                EF = 1.0

            prev = output_score

            output_score.backward(retain_graph=True)
            gradients = interpolated_input.grad * abs(EF)
            total_gradients += gradients

        final_gradients = total_gradients
        return (embedding_layer(input_ids) - baseline) * final_gradients

    input_text = generated_text
    ig = integrated_gradients(input_text, model, tokenizer, word_index)

    ig_scores = ig.squeeze().sum(dim=-1).detach().numpy()
    tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(input_text))
    ig_scores[word_index] = 0

    ig_scores = np.where(ig_scores < 0, 0, ig_scores)
    normalized_scores = ig_scores / np.sum(ig_scores)

    input_ids = tokenizer.encode(input_text, return_tensors='pt')
    outputs = model(input_ids)
    attentions = outputs.attentions

    sum_of_attentions = []
    number_of_layers = len(attentions)
    number_of_heads = attentions[0].shape[1]

    for layer in attentions:
        layer_attentions = []
        for head in range(number_of_heads):
            attention_values = layer[0, head][word_index].detach().numpy()
            layer_attentions.append(attention_values)
        sum_of_attentions.append(np.mean(layer_attentions, axis=0))

    avg_attention = np.mean(sum_of_attentions, axis=0)

    contribution_scores = [
        avg_attention[i] * normalized_scores[i] for i in range(len(avg_attention))
    ]

    token_contribution_dict = dict(zip(tokens, contribution_scores))

    word_contributions = {}
    current_word, current_score = "", 0.0
    for token, score in token_contribution_dict.items():
        if token.startswith('▁') or (current_word and not re.match(r'\w', token)):
            if current_word:
                word_contributions[current_word] = current_score
            current_word = token.lstrip('▁')
            current_score = score
        else:
            current_word += token
            current_score += score
    if current_word:
        word_contributions[current_word] = current_score

    def plot_word_contributions(contributions):
        cmap = plt.get_cmap("Greens")
        scores = list(contributions.values())
        min_score, max_score = min(scores), max(scores)

        def score_to_color(score):
            norm_score = (score - min_score) / (max_score - min_score + 1e-5)
            return mcolors.to_hex(cmap(norm_score)[:3])

        html_output = "<html><body>"
        for word, score in contributions.items():
            color_hex = score_to_color(score)
            html_output += f'<span style="background-color: {color_hex}; color: black; font-size: 20px; margin-right: 5px; padding: 2px; border-radius: 3px;">{word}</span>'
        html_output += "</body></html>"
        display(HTML(html_output))

    plot_word_contributions(word_contributions)

# Example usage
generated_text = "The quick brown fox jumps over the lazy dog."
word_index = 5  # Analyze the word "jumps"
AIEG(generated_text, word_index)