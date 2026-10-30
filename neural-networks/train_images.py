"""Train a software ResNet18 + ReLU classifier on user-supplied image folders."""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data', type=Path, help='Root containing train/ and validation/ class folders')
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch-size', type=int, default=16)
    parser.add_argument('--pretrained', action='store_true', help='Download ImageNet weights')
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error('--epochs must be positive')
    import torch
    from torch import nn
    from torch.utils.data import DataLoader
    from torchvision import datasets, transforms
    from torchvision.models import resnet18, ResNet18_Weights

    torch.manual_seed(11)
    transform = transforms.Compose([
        transforms.Resize((224, 224)), transforms.ToTensor(),
        transforms.Normalize([.485, .456, .406], [.229, .224, .225]),
    ])
    train = datasets.ImageFolder(args.data/'train', transform=transform)
    validation = datasets.ImageFolder(args.data/'validation', transform=transform)
    if train.class_to_idx != validation.class_to_idx:
        raise ValueError('Training and validation must contain identical class names')
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    weights = ResNet18_Weights.IMAGENET1K_V1 if args.pretrained else None
    model = resnet18(weights=weights)
    model.fc = nn.Sequential(nn.Linear(model.fc.in_features, 128), nn.ReLU(),
                             nn.Linear(128, len(train.classes)))
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = nn.CrossEntropyLoss()
    out = Path(__file__).resolve().parent/'runs'/'images'
    out.mkdir(parents=True, exist_ok=True)
    best = float('inf')
    for epoch in range(args.epochs):
        model.train()
        for images, labels in DataLoader(train, batch_size=args.batch_size, shuffle=True):
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images.to(device)), labels.to(device))
            loss.backward()
            optimizer.step()
        model.eval()
        total = 0.
        with torch.inference_mode():
            for images, labels in DataLoader(validation, batch_size=args.batch_size):
                total += criterion(model(images.to(device)), labels.to(device)).item()*len(labels)
        value = total/len(validation)
        print(f'Epoch {epoch+1}: validation loss {value:.5f}')
        if value < best:
            best = value
            torch.save({'model': model.state_dict(), 'classes': train.classes}, out/'model.pt')


if __name__ == '__main__':
    main()
