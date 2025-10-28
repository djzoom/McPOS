from src.main import main


def test_main_outputs_welcome_message(capsys):
    main()
    captured = capsys.readouterr()
    assert "Welcome to" in captured.out
