(() => {
  const size = { width: 512, height: 256 };
  const canvas = document.querySelector('#canvas');
  const context = canvas.getContext('2d', { willReadFrequently: true });
  const file = document.querySelector('#file');
  const filename = document.querySelector('#filename');
  const threshold = document.querySelector('#threshold');
  const contrast = document.querySelector('#contrast');
  const invert = document.querySelector('#invert');
  const fit = document.querySelector('#fit');
  const download = document.querySelector('#download');
  let source = null;

  function clear() {
    context.fillStyle = '#fff';
    context.fillRect(0, 0, size.width, size.height);
  }

  function drawSource() {
    clear();
    if (!source) return;
    const sourceRatio = source.width / source.height;
    const targetRatio = size.width / size.height;
    let width = size.width;
    let height = size.height;
    if (fit.value === 'contain') {
      if (sourceRatio > targetRatio) height = width / sourceRatio;
      else width = height * sourceRatio;
    } else if (fit.value === 'cover') {
      if (sourceRatio > targetRatio) width = height * sourceRatio;
      else height = width / sourceRatio;
    }
    context.drawImage(source, (size.width - width) / 2, (size.height - height) / 2, width, height);
  }

  function render() {
    document.querySelector('#thresholdValue').value = threshold.value;
    document.querySelector('#contrastValue').value = Number(contrast.value).toFixed(1).replace('.', ',');
    drawSource();
    if (!source) return;
    const data = context.getImageData(0, 0, size.width, size.height);
    const factor = Number(contrast.value);
    const limit = Number(threshold.value);
    for (let index = 0; index < data.data.length; index += 4) {
      const red = data.data[index];
      const green = data.data[index + 1];
      const blue = data.data[index + 2];
      let gray = 0.2126 * red + 0.7152 * green + 0.0722 * blue;
      gray = Math.max(0, Math.min(255, (gray - 128) * factor + 128));
      let value = gray >= limit ? 255 : 0;
      if (invert.checked) value = 255 - value;
      data.data[index] = value;
      data.data[index + 1] = value;
      data.data[index + 2] = value;
      data.data[index + 3] = 255;
    }
    context.putImageData(data, 0, 0);
  }

  file.addEventListener('change', () => {
    const selected = file.files[0];
    if (!selected) return;
    const image = new Image();
    image.onload = () => {
      source = image;
      filename.textContent = `${selected.name} (${image.width} × ${image.height})`;
      download.disabled = false;
      render();
      URL.revokeObjectURL(image.src);
    };
    image.src = URL.createObjectURL(selected);
  });

  [threshold, contrast, invert, fit].forEach(control => control.addEventListener('input', render));
  download.addEventListener('click', () => {
    canvas.toBlob(blob => {
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'nand-asset.png';
      link.click();
      URL.revokeObjectURL(link.href);
    }, 'image/png');
  });
  clear();
})();
