// PlayerController2D.cs — 2D 平台跳跃控制器模板
// 放 Assets/Scripts/Player/PlayerController.cs,挂到带 Rigidbody2D + CapsuleCollider2D 的对象
// 依赖: 无(旧 Input;换 Input System 时把 Input 行替换为 action 读取,见 references/09)
using UnityEngine;

[RequireComponent(typeof(Rigidbody2D))]
public class PlayerController2D : MonoBehaviour
{
    [Header("移动")]
    [SerializeField] private float _moveSpeed = 8f;
    [SerializeField] private float _jumpForce = 15f;
    [Header("手感(见 references/genres/2d-platformer.md)")]
    [SerializeField, Tooltip("离开平台后仍可起跳的时间")] private float _coyoteTime = 0.1f;
    [SerializeField, Tooltip("落地前按下跳跃的缓冲时间")] private float _jumpBuffer = 0.1f;
    [Header("检测")]
    [SerializeField] private LayerMask _groundLayer;
    [SerializeField] private float _groundCheckDist = 0.15f;

    private Rigidbody2D _rb;
    private float _coyoteTimer;
    private float _jumpBufferTimer;

    void Awake()
    {
        _rb = GetComponent<Rigidbody2D>();
    }

    void Update()
    {
        float x = Input.GetAxisRaw("Horizontal");
        _rb.linearVelocity = new Vector2(x * _moveSpeed, _rb.linearVelocity.y);  // 保留竖直速度

        // 跳跃缓冲: 记录按下时刻,窗口内保持可起跳
        _jumpBufferTimer = Input.GetButtonDown("Jump") ? _jumpBuffer : _jumpBufferTimer - Time.deltaTime;
        // 土狼时间: 落地刷新,离开地面后开始倒计时
        _coyoteTimer = IsGrounded() ? _coyoteTime : _coyoteTimer - Time.deltaTime;

        if (_jumpBufferTimer > 0f && _coyoteTimer > 0f)
        {
            _rb.linearVelocity = new Vector2(_rb.linearVelocity.x, _jumpForce);
            _jumpBufferTimer = 0f;
            _coyoteTimer = 0f;
        }

        // 松开跳跃键提前截断上升(低跳/高跳控制)
        if (Input.GetButtonUp("Jump") && _rb.linearVelocity.y > 0f)
        {
            _rb.linearVelocity = new Vector2(_rb.linearVelocity.x, _rb.linearVelocity.y * 0.5f);
        }
    }

    private bool IsGrounded()
    {
        return Physics2D.Raycast(transform.position, Vector2.down, _groundCheckDist, _groundLayer);
    }
}
