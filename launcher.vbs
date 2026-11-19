' AI Novel Studio Launcher
Set sh = CreateObject("WScript.Shell")

Function CheckServer()
    Dim http
    Set http = CreateObject("MSXML2.ServerXMLHTTP.6.0")
    CheckServer = False
    On Error Resume Next
    http.open "GET", "http://127.0.0.1:7860/api/health", False
    http.setTimeouts 500, 500, 500, 500
    http.send
    If Err.Number = 0 Then
        If http.status = 200 Then
            CheckServer = True
        End If
    End If
    On Error GoTo 0
End Function

If Not CheckServer() Then
    sh.CurrentDirectory = "C:\Users\corrz\Desktop\AI-NOVEL-STUDIO"
    sh.Run "cmd /c python api_server.py", 0, False
    
    ' 等待服务器启动就绪（最多等待 15 秒）
    For i = 1 To 30
        WScript.Sleep 500
        If CheckServer() Then
            Exit For
        End If
    Next
End If

sh.Run "http://127.0.0.1:7860/"
