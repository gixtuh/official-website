function clickAudio() {
    const click = document.getElementById("click")
    click.currentTime = 0;
    click.play();
}

function hoverAudio() {
    const hover = document.getElementById("hover")
    hover.currentTime = 0;
    hover.play()
}
document.querySelectorAll('button').forEach(button => {
    button.addEventListener('mouseover', hoverAudio);
});